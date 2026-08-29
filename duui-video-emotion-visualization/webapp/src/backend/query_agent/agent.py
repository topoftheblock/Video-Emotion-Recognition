"""The agent that turns a question into SQL.

`answer_question` runs a tool-use loop against an OpenAI-compatible
chat-completions endpoint. The model explores the schema by calling
`run_sql`, which hands back a short preview so it can check and correct
its own query, and finishes by calling `submit_answer`.

The final SQL is then re-executed here. Rows the model claims to have
seen are never trusted, and never reach the frontend.

Splitting "the model writes the query" from "this code runs it and
serializes the result" means a large result never has to travel through
the model's context, and the frontend never displays data that only the
model asserts exists.
"""

import json
from typing import Any

import openai

from ..config import (
    QUERY_AGENT_API_KEY,
    QUERY_AGENT_BASE_URL,
    QUERY_AGENT_MAX_TOOL_ITERATIONS,
    QUERY_AGENT_MODEL,
)
from .schema_context import SCHEMA_CONTEXT
from .sql_guard import SQLGuardError, run_read_only

OVERLAY_CHOICES = [
    "transcript",
    "bounding_boxes",
    "video_emotion",
    "audio_emotion",
    "text_emotion",
]

_SYSTEM_PROMPT = (
    SCHEMA_CONTEXT
    + """

## How to work

1. Use the `run_sql` tool to try queries and inspect a preview of the
   result (up to 20 rows + total row count). Iterate if the shape
   looks wrong (empty result, an obviously wrong join, etc.).
2. Once you're confident the query answers the question and follows
   the output contract above, call `submit_answer` exactly once with
   the final SQL, a one or two sentence explanation of what it
   computes, and the list of `overlays` the frontend should show while
   the user plays back the resulting clips.

## Choosing overlays

Pick ONLY the overlays that are actually relevant to what the question
is asking about -- the frontend will hide everything else so the user
isn't shown noise:
  - "transcript"      -> the question involves spoken words/text content
  - "text_emotion"     -> the question involves text/sentiment-of-words emotion
  - "video_emotion"    -> the question involves facial/visual emotion
  - "audio_emotion"    -> the question involves voice/prosody emotion
  - "bounding_boxes"   -> the question is about who/where someone is on screen,
                          or video_emotion is selected (labels render on the boxes)

A "divergence between video and text emotion" question should select
["transcript", "video_emotion", "text_emotion", "bounding_boxes"], for
example -- not audio_emotion, since that isn't what the user asked
about.

If `run_sql` returns an error, read it, fix the query, and try again.
Never call `submit_answer` with a query you haven't successfully run
via `run_sql` at least once.
"""
)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Run a read-only SELECT query against the database and get back "
                "a preview (first 20 rows, columns, total row count, or an error "
                "message). Use this to explore and validate queries before "
                "submitting a final answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "A single SELECT (or WITH ... SELECT) statement."
                        ),
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": (
                "Submit the final SQL query, explanation, and display overlays that "
                "answer the user's question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "The final SELECT/WITH query, following the output "
                            "contract."
                        ),
                    },
                    "explanation": {
                        "type": "string",
                        "description": (
                            "One or two sentences describing what the "
                            "query answers, in plain language."
                        ),
                    },
                    "overlays": {
                        "type": "array",
                        "items": {"type": "string", "enum": OVERLAY_CHOICES},
                        "description": (
                            "Which display overlays the frontend should enable for "
                            "these results."
                        ),
                    },
                },
                "required": ["sql", "explanation", "overlays"],
            },
        },
    },
]


class QueryAgentError(RuntimeError):
    """Raised when the agent cannot produce a usable answer."""


def _preview_tool_result(sql: str) -> dict[str, Any]:
    """Run one exploratory query for the model, and report the outcome.

    Capped to a short preview: the model needs the shape of a result,
    not the result itself.

    Args:
        sql: The statement the model asked to run.

    Returns:
        The preview, or `{"ok": False, "error": ...}` when the guard
        rejected the query. A rejection is handed back for the model to
        correct, rather than raised.
    """
    try:
        columns, rows, truncated = run_read_only(sql, row_limit=20)
        return {
            "ok": True,
            "columns": columns,
            "rows": rows,
            "row_count_shown": len(rows),
            "more_rows_exist": truncated,
        }
    except SQLGuardError as exc:
        return {"ok": False, "error": str(exc)}


def answer_question(question: str) -> dict[str, Any]:
    """Run the agent loop for one question, and return the answer.

    Args:
        question: The user's question, in natural language.

    Returns:
        The final `sql` and `explanation`, the `overlays` the frontend
        should show, and the result itself as `columns`, `rows`,
        `row_count` and `truncated`.

    Raises:
        QueryAgentError: If no API key is configured, the API call
            fails, the model never submits an answer within the
            allotted steps, or its final query fails validation.
    """
    if not QUERY_AGENT_API_KEY:
        raise QueryAgentError("DUUI_QUERY_API_KEY is not configured (set it in .env).")

    client = openai.OpenAI(api_key=QUERY_AGENT_API_KEY, base_url=QUERY_AGENT_BASE_URL)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {question}"},
    ]

    for _ in range(QUERY_AGENT_MAX_TOOL_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=QUERY_AGENT_MODEL,
                max_tokens=2048,
                tools=_TOOLS,
                messages=messages,
            )
        except openai.APIError as exc:
            # Auth failures, rate limits, a bad model name and network
            # errors alike. All are faults of the API call rather than
            # of the user's question, so they surface as a clean error
            # instead of an unhandled 500.
            raise QueryAgentError(f"LLM API call failed: {exc}") from exc

        message = response.choices[0].message
        # Only the content and the tool calls are carried back into the
        # conversation. Any other field a provider returns alongside
        # them is dropped rather than fed back, so the loop depends on
        # nothing outside the documented response shape.
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": message.tool_calls,
            }
        )

        if not message.tool_calls:
            # The model answered in prose instead of calling a tool.
            # Nudge it back rather than failing outright.
            messages.append(
                {
                    "role": "user",
                    "content": "Please continue by calling run_sql or submit_answer.",
                }
            )
            continue

        submit_call = next(
            (t for t in message.tool_calls if t.function.name == "submit_answer"), None
        )
        if submit_call is not None:
            return _finalize(json.loads(submit_call.function.arguments))

        for call in message.tool_calls:
            if call.function.name == "run_sql":
                args = json.loads(call.function.arguments)
                result = _preview_tool_result(args.get("sql", ""))
            else:
                result = {"ok": False, "error": f"Unknown tool {call.function.name}"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )

    raise QueryAgentError(
        "The agent could not settle on a final query within the allotted steps. "
        "Try rephrasing the question."
    )


def _finalize(submission: dict[str, Any]) -> dict[str, Any]:
    """Re-run the model's final query, and build the response.

    An overlay not in `OVERLAY_CHOICES` is dropped rather than passed
    on: the frontend switches on these names, so an unknown one would
    silently enable nothing.

    Args:
        submission: The arguments the model gave `submit_answer`.

    Returns:
        The payload the route returns.

    Raises:
        QueryAgentError: If the final query fails validation.
    """
    sql = submission.get("sql", "")
    explanation = submission.get("explanation", "")
    overlays = [o for o in submission.get("overlays", []) if o in OVERLAY_CHOICES]

    try:
        columns, rows, truncated = run_read_only(sql)
    except SQLGuardError as exc:
        raise QueryAgentError(f"Final query failed validation: {exc}") from exc

    return {
        "sql": sql,
        "explanation": explanation,
        "overlays": overlays,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }
