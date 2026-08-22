"""
Tests for the identity rules the schema and the parsers share: videos
are keyed by filename, everything under a video is keyed by
(video_id, the CAS's own xmi:id), and models are keyed by what a model
actually is.

These are the rules that stop two CAS files from merging into one
another. The bug they exist to prevent was not hypothetical: nine files
whose DocumentMetaData all sat at xmi:id 3 claimed one `videos` row
between them, and 4,420 of 42,939 emotion ids collided across those
files, each one either dropped or overwritten with another video's
reading.

DB-backed and rolled back by the shared fixtures -- nothing here
commits.
"""

import pytest

from importer.parsers import model as model_parser
from importer.parsers import video as video_parser


@pytest.fixture
def video_row(db_cursor):
    """Insert a video by filename the way parsers/video.py does."""

    def insert(filename, **columns):
        db_cursor.execute(
            """
            INSERT INTO videos (filename, duration, fps)
            VALUES (%s, %s, %s)
            ON CONFLICT (filename) DO UPDATE SET
                duration = EXCLUDED.duration, fps = EXCLUDED.fps
            RETURNING video_id
            """,
            (filename, columns.get("duration"), columns.get("fps")),
        )
        return db_cursor.fetchone()[0]

    return insert


def test_the_same_filename_is_one_video(video_row, db_cursor):
    first = video_row("teil_000.mp4", duration=10.0)
    second = video_row("teil_000.mp4", duration=20.0)

    assert first == second
    db_cursor.execute("SELECT duration FROM videos WHERE video_id = %s", (first,))
    # Re-importing a file updates its row rather than adding another.
    assert db_cursor.fetchone()[0] == 20.0


def test_different_filenames_are_different_videos(video_row):
    assert video_row("teil_000.mp4") != video_row("teil_001.mp4")


def test_two_videos_can_hold_the_same_xmi_id(video_row, db_cursor):
    # xmi:id 16621 is a real collision from the Bundestag corpus:
    # teil_000 and teil_003 both use it, for different readings.
    first = video_row("teil_000.mp4")
    second = video_row("teil_003.mp4")

    for video_id, valence in ((first, 0.065), (second, 0.0)):
        db_cursor.execute(
            """
            INSERT INTO base_emotions (video_id, emotion_id, modality, valence)
            VALUES (%s, 16621, 'video', %s)
            ON CONFLICT (video_id, emotion_id) DO UPDATE SET valence = EXCLUDED.valence
            """,
            (video_id, valence),
        )

    db_cursor.execute(
        "SELECT video_id, valence FROM base_emotions WHERE emotion_id = 16621 "
        "AND video_id IN (%s, %s) ORDER BY video_id",
        (first, second),
    )
    assert db_cursor.fetchall() == [(first, 0.065), (second, 0.0)]


def test_a_person_reference_cannot_cross_videos(video_row, db_cursor):
    first = video_row("teil_000.mp4")
    second = video_row("teil_003.mp4")
    db_cursor.execute(
        "INSERT INTO persons (video_id, person_id, clip_label) VALUES (%s, 1, 'person_1')",
        (first,),
    )

    # The merge this schema exists to prevent: another video's row
    # pointing at this video's person.
    with pytest.raises(Exception) as excinfo:
        db_cursor.execute(
            "INSERT INTO base_emotions (video_id, emotion_id, person_id, modality) "
            "VALUES (%s, 5, 1, 'video')",
            (second,),
        )
    assert "foreign key" in str(excinfo.value).lower()


def test_deleting_a_video_takes_its_whole_subtree(video_row, db_cursor):
    """What `--on-existing replace` relies on."""
    keep = video_row("teil_001.mp4")
    drop = video_row("teil_000.mp4")
    for video_id in (keep, drop):
        db_cursor.execute(
            "INSERT INTO persons (video_id, person_id) VALUES (%s, 1)", (video_id,)
        )
        db_cursor.execute(
            "INSERT INTO base_emotions (video_id, emotion_id, person_id, modality) "
            "VALUES (%s, 7, 1, 'video')",
            (video_id,),
        )
        db_cursor.execute(
            "INSERT INTO emotion_scores (video_id, emotion_id, label, score) "
            "VALUES (%s, 7, 'Happiness', 0.9)",
            (video_id,),
        )

    db_cursor.execute("DELETE FROM videos WHERE video_id = %s", (drop,))

    for table in ("persons", "base_emotions", "emotion_scores"):
        db_cursor.execute(f"SELECT count(*) FROM {table} WHERE video_id = %s", (drop,))
        assert db_cursor.fetchone()[0] == 0, f"{table} kept rows for the deleted video"
        db_cursor.execute(f"SELECT count(*) FROM {table} WHERE video_id = %s", (keep,))
        assert db_cursor.fetchone()[0] == 1, f"{table} lost rows for the other video"


def test_models_are_shared_across_videos_not_duplicated(db_cursor):
    class FakeMetaData:
        def __init__(self, name):
            self.ModelName = name
            self.ModelVersion = None
            self.Source = None

    # Two "CAS files" naming the same model: one row, and both imports
    # learn the same model_id for their own xmi:id.
    contexts = []
    for xmi_id, cas in ((11, [FakeMetaData("insightface")]), (77, [FakeMetaData("insightface")])):
        context = {}
        for metadata in cas:
            db_cursor.execute(
                """
                INSERT INTO models (name, version, source) VALUES (%s, %s, %s)
                ON CONFLICT (name, version, source) DO UPDATE SET name = EXCLUDED.name
                RETURNING model_id
                """,
                (metadata.ModelName, metadata.ModelVersion, metadata.Source),
            )
            context[xmi_id] = db_cursor.fetchone()[0]
        contexts.append(context)

    assert list(contexts[0].values()) == list(contexts[1].values())
    db_cursor.execute(
        "SELECT count(*) FROM models WHERE name = 'insightface' "
        "AND version IS NULL AND source IS NULL"
    )
    assert db_cursor.fetchone()[0] == 1


def test_parsers_expose_the_identity_read_both_paths_need():
    # pipeline.py reads the filename off the raw XML to decide
    # skip/replace; parsers/video.py reads it off the loaded CAS. Both
    # have to exist, and both have to follow MultimediaElement ->
    # DocumentMetaData, or the decision and the row could disagree.
    assert callable(video_parser.read_identity)
    assert callable(model_parser.parse)
