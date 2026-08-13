"""Parses GlobalPerson and (video-local) Person rows.

Also builds the face_id/voice_id -> person_id lookup maps that other
parsers (embedding, presence, detection, emotion) need when a
pipeline only encodes the person link as a string rather than a
direct FeatureStructure reference -- e.g. a real observed label:

    label="voice:SPEAKER_00|face:face_7|score:0.83"

with matching identity:FaceIdentity.faceId="face_7" /
identity:VoiceIdentity.voiceId="SPEAKER_00" elsewhere in the CAS.
These maps are stored on the shared pipeline `context` dict so later
parser steps (which run after this one -- see parsers/__init__.py)
can use them via identity_resolution.py.
"""

from ..cas_views import select_across_views
from ..config import TYPES
from ..identity_resolution import parse_person_label
from ..typesystem import get_xmi_id


def _parse_global_persons(cas, cursor, conn):
    for g_person in select_across_views(cas, TYPES["global_person"]):
        gp_id = get_xmi_id(g_person)
        cursor.execute(
            "INSERT INTO global_persons (global_person_id, real_name) VALUES (%s, %s) "
            "ON CONFLICT (global_person_id) DO NOTHING",
            (gp_id, getattr(g_person, "real_name", getattr(g_person, "name", None))),
        )


def _parse_persons(cas, cursor, conn, video_id, context):
    face_id_to_person_id = context.setdefault("face_id_to_person_id", {})
    voice_id_to_person_id = context.setdefault("voice_id_to_person_id", {})

    for person in select_across_views(cas, TYPES["person"]):
        person_id = get_xmi_id(person)

        global_person_id = get_xmi_id(getattr(person, "globalPerson", None))
        label = getattr(person, "label", None)
        label_parts = parse_person_label(label)

        # Prefer an explicit clip_label; otherwise the human-readable
        # personId ("person_1"); otherwise fall back to the raw
        # encoded label string.
        clip_label = getattr(
            person, "clip_label", getattr(person, "personId", label)
        )
        match_score = getattr(person, "match_score", label_parts.get("score"))

        cursor.execute(
            """
            INSERT INTO persons (person_id, video_id, global_person_id, clip_label, match_score)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
            """,
            (
                person_id,
                video_id,
                global_person_id,
                clip_label,
                match_score,
            ),
        )

        if "face" in label_parts:
            face_id_to_person_id[label_parts["face"]] = person_id
        if "voice" in label_parts:
            voice_id_to_person_id[label_parts["voice"]] = person_id


def parse(cas, cursor, conn, context):
    video_id = context.get("global_video_id")
    _parse_global_persons(cas, cursor, conn)
    _parse_persons(cas, cursor, conn, video_id, context)
