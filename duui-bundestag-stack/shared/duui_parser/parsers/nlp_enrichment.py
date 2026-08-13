"""
NLP integration: backfills `linguistic_tokens.pos_tag`/`.ner_label`.

Both columns have existed in the schema from the start, but the real
Bundestag CAS never sets them (confirmed empty on every real CAS this
parser has been run against -- the linguistic annotation step simply
isn't part of that pipeline run), so `token.py` inserts NULL for both.
This step runs a real NLP model (spaCy) over each sentence's
*reconstructed* text -- reusing the same word-token rows already in
the DB rather than needing the original raw transcript -- and writes
POS/NER back onto the token rows that were already inserted.

Alignment is inherently approximate: our tokens come from WhisperX
(ASR word-timestamps), not spaCy's own tokenizer, so token boundaries
can disagree (e.g. WhisperX's "Dank." as one token vs spaCy splitting
it into "Dank" + "."). Each of our tokens is matched to whichever
spaCy token/entity span overlaps it the most in the reconstructed
text, rather than requiring an exact boundary match.
"""

from ..config import ENABLE_NLP_ENRICHMENT, SPACY_MODEL

_nlp = None
_load_attempted = False


def _get_nlp():
    """Lazily load and cache the spaCy pipeline for the whole process
    -- reloading a model per video would dominate import time."""
    global _nlp, _load_attempted
    if _load_attempted:
        return _nlp
    _load_attempted = True
    try:
        import spacy

        _nlp = spacy.load(SPACY_MODEL)
    except Exception as exc:
        print(
            f"[duui_parser] warning: could not load spaCy model {SPACY_MODEL!r} "
            f"({exc}); skipping NLP enrichment for this run. "
            f"Install it with: python -m spacy download {SPACY_MODEL}"
        )
        _nlp = None
    return _nlp


def _reconstruct_sentence(cursor, video_id, begin_offset, end_offset):
    """
    Joins every token in [begin_offset, end_offset) with single spaces
    into one string, and returns each token's (token_id, start, end)
    character span *within that reconstructed string* -- not the
    original transcript offsets, since spaCy tokenizes the string we
    hand it, not the source document.
    """
    cursor.execute(
        """
        SELECT token_id, word FROM linguistic_tokens
        WHERE video_id = %s AND begin_offset >= %s AND end_offset <= %s
        ORDER BY begin_offset
        """,
        (video_id, begin_offset, end_offset),
    )
    rows = cursor.fetchall()

    parts = []
    spans = []
    pos = 0
    for token_id, word in rows:
        if not word:
            continue
        if parts:
            parts.append(" ")
            pos += 1
        start = pos
        parts.append(word)
        pos += len(word)
        spans.append((token_id, start, pos))
    return "".join(parts), spans


def _best_overlapping_token(doc, start, end):
    best, best_overlap = None, 0
    for tok in doc:
        tok_start, tok_end = tok.idx, tok.idx + len(tok.text)
        overlap = min(end, tok_end) - max(start, tok_start)
        if overlap > best_overlap:
            best_overlap, best = overlap, tok
    return best


def _overlapping_entity_label(doc, start, end):
    for ent in doc.ents:
        if max(start, ent.start_char) < min(end, ent.end_char):
            return ent.label_
    return None


def parse(cas, cursor, conn, context):
    if not ENABLE_NLP_ENRICHMENT:
        return

    nlp = _get_nlp()
    if nlp is None:
        return

    video_id = context.get("global_video_id")
    if video_id is None:
        return

    cursor.execute(
        """
        SELECT segment_id, begin_offset, end_offset FROM segments
        WHERE video_id = %s AND kind = 'sentence'
          AND begin_offset IS NOT NULL AND end_offset IS NOT NULL
        """,
        (video_id,),
    )
    sentences = cursor.fetchall()

    for _segment_id, begin_offset, end_offset in sentences:
        text, spans = _reconstruct_sentence(cursor, video_id, begin_offset, end_offset)
        if not text.strip() or not spans:
            continue

        doc = nlp(text)
        for token_id, start, end in spans:
            tok = _best_overlapping_token(doc, start, end)
            pos_tag = tok.pos_ if tok is not None else None
            ner_label = _overlapping_entity_label(doc, start, end)
            if pos_tag is None and ner_label is None:
                continue
            cursor.execute(
                """
                UPDATE linguistic_tokens
                SET pos_tag = COALESCE(%s, pos_tag), ner_label = COALESCE(%s, ner_label)
                WHERE token_id = %s
                """,
                (pos_tag, ner_label, token_id),
            )
