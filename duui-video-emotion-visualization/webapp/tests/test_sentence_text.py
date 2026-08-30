"""Tests for the subtitle assembly in `queries/videos.py`.

Sentence text is not stored. It is rebuilt from the token rows every
time a video is loaded, matched by time overlap rather than by segment
reference — see `assemble_sentence_text` for why. That makes it the one
piece of real logic in the payload builder, and it needs no database.
"""

from backend.queries.videos import assemble_sentence_text


def _tok(word: str | None, start: float | None) -> dict:
    """Build the two token fields the assembly actually reads."""
    return {"word": word, "start_time": start}


def test_joins_tokens_inside_the_window_in_order() -> None:
    """Tokens within the sentence become its text, in time order."""
    sentence = {"start_time": 1.0, "end_time": 3.0}
    tokens = [_tok("guten", 1.0), _tok("tag", 2.0)]
    assert assemble_sentence_text(sentence, tokens) == "guten tag"


def test_window_is_inclusive_at_both_ends() -> None:
    """A token exactly on either bound belongs to the sentence."""
    sentence = {"start_time": 1.0, "end_time": 3.0}
    tokens = [_tok("start", 1.0), _tok("end", 3.0)]
    assert assemble_sentence_text(sentence, tokens) == "start end"


def test_excludes_tokens_outside_the_window() -> None:
    """Neighbouring sentences' words do not leak in."""
    sentence = {"start_time": 1.0, "end_time": 3.0}
    tokens = [_tok("before", 0.5), _tok("inside", 2.0), _tok("after", 3.5)]
    assert assemble_sentence_text(sentence, tokens) == "inside"


def test_skips_tokens_with_no_start_time() -> None:
    """An untimed token cannot be placed, so it is left out."""
    sentence = {"start_time": 0.0, "end_time": 5.0}
    tokens = [_tok("kept", 1.0), _tok("untimed", None)]
    assert assemble_sentence_text(sentence, tokens) == "kept"


def test_drops_empty_words_rather_than_doubling_spaces() -> None:
    """An empty word would otherwise show as a gap in the subtitle."""
    sentence = {"start_time": 0.0, "end_time": 5.0}
    tokens = [_tok("a", 1.0), _tok("", 2.0), _tok(None, 2.5), _tok("b", 3.0)]
    assert assemble_sentence_text(sentence, tokens) == "a b"


def test_returns_empty_string_when_the_sentence_has_no_bounds() -> None:
    """A segment may carry no times: no subtitle, and not an error."""
    assert assemble_sentence_text({"start_time": None, "end_time": 3.0}, []) == ""
    assert assemble_sentence_text({"start_time": 1.0, "end_time": None}, []) == ""


def test_no_tokens_gives_empty_string() -> None:
    """A sentence with no words in range assembles to nothing."""
    assert assemble_sentence_text({"start_time": 1.0, "end_time": 3.0}, []) == ""
