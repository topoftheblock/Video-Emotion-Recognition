"""One real CAS, through the whole importer, into the database.

Every other test in this suite exercises a piece: path resolution, the
video placement, the identity rules the schema enforces. None of them
runs a parser. Before this file, the eleven `parsers/*` modules and
`pipeline.py` had no test that executed their bodies at all — what
caught a regression was a person importing the sample by hand.

This drives the shipped sample through `run_many` exactly as the
container does, and asserts what landed in each table. It is one test
rather than eleven because a parser that silently stops writing shows up
here as a count that moved, which is the failure that matters; a broken
join between two parsers shows up here and would not in a unit test.

The counts below are properties of the sample, which is committed and
does not change. A count that moves means either the sample changed or a
parser did.

Database-backed. It imports with `replace`, so it does not care whether
a previous run left the video behind, and it removes its own rows
afterwards.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from importer import pipeline, video_files
from importer.config import RESOURCES_DIR
from importer.db import delete_video, find_video_by_filename, get_db_connection

SAMPLE_DIR = RESOURCES_DIR / "sample-input"
SAMPLE_CAS = SAMPLE_DIR / "full_2sek_with_person.xmi"
SAMPLE_VIDEO = "first2.mp4"

#: What the sample produces, per table, for its one video. Measured
#: against the committed file; see the module docstring.
EXPECTED_ROWS = {
    "persons": 1,
    "segments": 3,
    "linguistic_tokens": 2,
    "presences": 20,
    "face_detections": 119,
    "person_detections": 123,
    "base_emotions": 122,
    "emotion_scores": 996,
    "face_embeddings": 19,
    # The sample carries no voice embeddings. That branch of
    # parsers/embedding.py is therefore not covered here, and is the one
    # place this test leaves open.
    "voice_embeddings": 0,
}


@pytest.fixture
def imported_sample(
    db_available: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[int]:
    """Import the sample, hand back its video id, then remove it again.

    The video store is redirected into a temporary directory: unset, it
    defaults to a path relative to the working directory, and the import
    would write into the mounted source tree.
    """
    if not db_available:
        pytest.skip("no database available")

    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(tmp_path / "videos"))
    monkeypatch.setattr(pipeline, "INPUT_VIDEO_DIR", str(SAMPLE_DIR))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(max(job_run_id), 0) FROM job_runs")
        job_high_water = cur.fetchone()[0]
    conn.close()

    succeeded, failed = pipeline.run_many([str(SAMPLE_CAS)], on_existing="replace")
    assert not failed, f"the sample failed to import: {failed}"
    assert len(succeeded) == 1

    video_id = find_video_by_filename(SAMPLE_VIDEO)
    assert video_id is not None, "the import reported success but wrote no video row"

    try:
        yield video_id
    finally:
        delete_video(video_id)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM job_runs WHERE job_run_id > %s", (job_high_water,)
                )
            conn.commit()
        finally:
            conn.close()


def _count(video_id: int, table: str) -> int:
    """Rows in one table belonging to one video."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT count(*) FROM {table} WHERE video_id = %s", (video_id,)
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def test_every_parser_wrote_what_the_sample_holds(imported_sample: int) -> None:
    """Each table receives exactly the rows the sample describes.

    Asserted as one dict rather than a test apiece, so a failure names
    every table that moved instead of stopping at the first.
    """
    actual = {table: _count(imported_sample, table) for table in EXPECTED_ROWS}

    assert actual == EXPECTED_ROWS


def test_the_video_row_carries_what_the_cas_declared(imported_sample: int) -> None:
    """The video is keyed by filename, and its metadata carried over."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT filename, processed_at FROM videos WHERE video_id = %s",
                (imported_sample,),
            )
            filename, processed_at = cur.fetchone()
    finally:
        conn.close()

    assert filename == SAMPLE_VIDEO
    assert processed_at is not None, "the importer records when a video was processed"


def test_the_companion_video_is_placed_in_the_store(
    imported_sample: int, tmp_path: Path
) -> None:
    """The file the webapp plays is copied beside the rows."""
    assert (tmp_path / "videos" / SAMPLE_VIDEO).is_file()


def test_sentence_text_is_assembled_from_the_tokens(imported_sample: int) -> None:
    """The transcript survives the trip into segments and tokens."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM linguistic_tokens "
                "WHERE video_id = %s AND word IS NOT NULL AND word <> ''",
                (imported_sample,),
            )
            worded = cur.fetchone()[0]
    finally:
        conn.close()

    assert worded == EXPECTED_ROWS["linguistic_tokens"]


def test_emotions_carry_a_modality_and_a_granularity(imported_sample: int) -> None:
    """The webapp groups and filters on both, so neither may be null."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM base_emotions WHERE video_id = %s "
                "AND (modality IS NULL OR granularity IS NULL)",
                (imported_sample,),
            )
            untagged = cur.fetchone()[0]
    finally:
        conn.close()

    assert untagged == 0


def test_the_run_is_recorded_as_finished(imported_sample: int) -> None:
    """`run_many` opens a job run and closes it; the webapp reads it."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, progress_current, progress_total FROM job_runs "
                "WHERE job = 'importer' ORDER BY job_run_id DESC LIMIT 1"
            )
            status, current, total = cur.fetchone()
    finally:
        conn.close()

    assert status == "finished"
    assert (current, total) == (1, 1)
