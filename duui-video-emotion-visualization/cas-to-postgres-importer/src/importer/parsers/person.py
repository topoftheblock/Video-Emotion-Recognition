"""Reads the people in one video, and builds the lookup maps.

`persons.global_person_id` is deliberately left NULL here, and
`identity:GlobalPerson` is not read from the CAS at all. Linking people
across videos is computed from embeddings by a separate, explicitly run
job, which clears and rebuilds both that column and `global_persons`
corpus-wide — so anything the importer wrote there would be discarded
on its next run. Not reading the type also drops a "type not found"
warning from every import: `GlobalPerson` is absent from the shipped
typesystems, and no real CAS seen here has populated it.

This step also builds the face-id and voice-id lookup maps that the
embedding, presence, detection and emotion steps need when a pipeline
encodes the person link only as a string rather than as a direct
reference. A real observed label:

    label="voice:SPEAKER_00|face:face_7|score:0.83"

with matching `FaceIdentity.faceId="face_7"` and
`VoiceIdentity.voiceId="SPEAKER_00"` elsewhere in the CAS. The maps go
into the shared context, so the steps that run after this one can use
them through `cas/person_resolution.py`.
"""

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.person_resolution import parse_person_label
from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id
from ..cas.views import select_across_views


def _parse_persons(
    cas: Cas, cursor: Cursor, video_id: int | None, context: dict
) -> None:
    """Insert each person, and record their face and voice keys."""
    face_id_to_person_id = context.setdefault("face_id_to_person_id", {})
    voice_id_to_person_id = context.setdefault("voice_id_to_person_id", {})

    for person in select_across_views(cas, TYPES["person"]):
        person_id = get_xmi_id(person)

        label = getattr(person, "label", None)
        label_parts = parse_person_label(label)

        # Prefer an explicit clip_label, then the readable personId
        # such as "person_1", and fall back to the raw label string.
        clip_label = getattr(person, "clip_label", getattr(person, "personId", label))
        audio_video_match_score = getattr(
            person, "match_score", label_parts.get("score")
        )

        cursor.execute(
            """
            INSERT INTO persons
                (person_id, video_id, clip_label, audio_video_match_score)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (video_id, person_id) DO NOTHING
            """,
            (
                person_id,
                video_id,
                clip_label,
                audio_video_match_score,
            ),
        )

        if "face" in label_parts:
            face_id_to_person_id[label_parts["face"]] = person_id
        if "voice" in label_parts:
            voice_id_to_person_id[label_parts["voice"]] = person_id


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert this video's people and build the person lookup maps.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    video_id = context.get("global_video_id")
    _parse_persons(cas, cursor, video_id, context)
