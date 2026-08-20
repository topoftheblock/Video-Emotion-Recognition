"""
Tests for the subtitle assembly in src/backend/queries/videos.py.

Sentence text isn't stored -- it's rebuilt from the token rows every
time a video is loaded, by time overlap rather than by segment_id (see
assemble_sentence_text's docstring for why). That makes it the one
piece of real logic in the payload builder, and it needs no database.
"""

from backend.queries.videos import assemble_sentence_text


def _tok(word, start):
    return {"word": word, "start_time": start}


def test_joins_tokens_inside_the_window_in_order():
    sentence = {"start_time": 1.0, "end_time": 3.0}
    tokens = [_tok("guten", 1.0), _tok("tag", 2.0)]
    assert assemble_sentence_text(sentence, tokens) == "guten tag"


def test_window_is_inclusive_at_both_ends():
    sentence = {"start_time": 1.0, "end_time": 3.0}
    tokens = [_tok("start", 1.0), _tok("end", 3.0)]
    assert assemble_sentence_text(sentence, tokens) == "start end"


def test_excludes_tokens_outside_the_window():
    sentence = {"start_time": 1.0, "end_time": 3.0}
    tokens = [_tok("before", 0.5), _tok("inside", 2.0), _tok("after", 3.5)]
    assert assemble_sentence_text(sentence, tokens) == "inside"


def test_skips_tokens_with_no_start_time():
    sentence = {"start_time": 0.0, "end_time": 5.0}
    tokens = [_tok("kept", 1.0), _tok("untimed", None)]
    assert assemble_sentence_text(sentence, tokens) == "kept"


def test_drops_empty_words_rather_than_doubling_spaces():
    sentence = {"start_time": 0.0, "end_time": 5.0}
    tokens = [_tok("a", 1.0), _tok("", 2.0), _tok(None, 2.5), _tok("b", 3.0)]
    assert assemble_sentence_text(sentence, tokens) == "a b"


def test_returns_empty_string_when_the_sentence_has_no_bounds():
    # Segments can carry NULL times; the frontend renders "" as no
    # subtitle, which is the wanted behaviour rather than an error.
    assert assemble_sentence_text({"start_time": None, "end_time": 3.0}, []) == ""
    assert assemble_sentence_text({"start_time": 1.0, "end_time": None}, []) == ""


def test_no_tokens_gives_empty_string():
    assert assemble_sentence_text({"start_time": 1.0, "end_time": 3.0}, []) == ""
