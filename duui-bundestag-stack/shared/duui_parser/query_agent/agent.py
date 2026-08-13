"""
The natural-language -> SQL agent.

`answer_question(question)` runs a tool-use loop against an
OpenAI-compatible chat-completions endpoint (configured via
QUERY_AGENT_BASE_URL/QUERY_AGENT_MODEL -- this project points it at a
university-hosted Qwen3-VL gateway, not Anthropic): the model explores
the schema by calling `run_sql` (getting back a small
preview + row count so it can sanity-check and fix its own query),
then finalizes with `submit_answer` once it's confident. We then
re-execute that final SQL ourselves (never trusting rows the model
claims to have seen) to build the actual response returned to the
frontend.

Splitting "the model writes the query" from "our code runs the query
and serializes results" means a large result set never has to round
-trip through the model's context window, and the frontend never
displays data the model merely claims exists.
"""

import json

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
    "fused_emotion",
]

_SYSTEM_PROMPT = SCHEMA_CONTEXT + """

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
  - "fused_emotion"    -> the question involves an overall/combined/aggregated emotion

A "divergence between video and text emotion" question should select
["transcript", "video_emotion", "text_emotion", "bounding_boxes"], for
example -- not audio_emotion or fused_emotion, since those aren't what
the user asked about.

If `run_sql` returns an error, read it, fix the query, and try again.
Never call `submit_answer` with a query you haven't successfully run
via `run_sql` at least once.
"""

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
                    "sql": {"type": "string", "description": "A single SELECT (or WITH ... SELECT) statement."}
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "Submit the final SQL query, explanation, and display overlays that answer the user's question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "The final SELECT/WITH query, following the output contract."},
                    "explanation": {"type": "string", "description": "One or two sentences describing what the query answers, in plain language."},
                    "overlays": {
                        "type": "array",
                        "items": {"type": "string", "enum": OVERLAY_CHOICES},
                        "description": "Which display overlays the frontend should enable for these results.",
                    },
                },
                "required": ["sql", "explanation", "overlays"],
            },
        },
    },
]


class QueryAgentError(RuntimeError):
    pass


def _preview_tool_result(sql: str) -> dict:
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


def answer_question(question: str) -> dict:
    """
    Run the agent loop for one user question. Returns:
        {
          "sql": str,
          "explanation": str,
          "overlays": [str, ...],
          "columns": [str, ...],
          "rows": [dict, ...],
          "row_count": int,
          "truncated": bool,
        }
    Raises QueryAgentError on failure (bad API key, model never
    submitted an answer, final SQL invalid, etc).
    """
    if not QUERY_AGENT_API_KEY:
        raise QueryAgentError(
            "DUUI_QUERY_API_KEY is not configured (set it in .env)."
        )

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
            # Covers auth failures, rate limits, bad model name, and
            # network-level errors alike -- all of these are questions
            # about the API call itself, not about the user's question,
            # so they surface as a clean QueryAgentError (-> HTTP 422)
            # instead of an unhandled 500.
            raise QueryAgentError(f"LLM API call failed: {exc}") from exc

        message = response.choices[0].message
        # Qwen3's "thinking" trace comes back as a separate
        # reasoning_content field alongside content/tool_calls -- never
        # part of the OpenAI response schema itself, so it's simply
        # ignored here rather than fed back into the conversation.
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": message.tool_calls,
            }
        )

        if not message.tool_calls:
            # Model responded with plain text instead of using a tool --
            # nudge it back on track rather than failing outright.
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


def _finalize(submission: dict) -> dict:
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
