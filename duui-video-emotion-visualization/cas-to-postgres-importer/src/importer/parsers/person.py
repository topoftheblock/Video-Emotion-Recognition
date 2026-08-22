"""Parses (video-local) Person rows.

`persons.global_person_id` is deliberately left NULL here, and
`identity:GlobalPerson` is not read from the CAS at all. Cross-video
identity is computed from embeddings by a separate, explicitly-run job
(see global-identity-linker/) which clears and rebuilds
both `global_persons` and this column corpus-wide -- so anything the
importer wrote into them would be discarded on its next run anyway.
Not reading the type also drops a "type not found in typesystem"
warning on every import: `GlobalPerson` is absent from the shipped
typesystems, and no real CAS this parser has run against populated it.

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


def _parse_persons(cas, cursor, video_id, context):
    face_id_to_person_id = context.setdefault("face_id_to_person_id", {})
    voice_id_to_person_id = context.setdefault("voice_id_to_person_id", {})

    for person in select_across_views(cas, TYPES["person"]):
        person_id = get_xmi_id(person)

        label = getattr(person, "label", None)
        label_parts = parse_person_label(label)

        # Prefer an explicit clip_label; otherwise the human-readable
        # personId ("person_1"); otherwise fall back to the raw
        # encoded label string.
        clip_label = getattr(
            person, "clip_label", getattr(person, "personId", label)
        )
        audio_video_match_score = getattr(person, "match_score", label_parts.get("score"))

        cursor.execute(
            """
            INSERT INTO persons (person_id, video_id, clip_label, audio_video_match_score)
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


def parse(cas, cursor, context):
    video_id = context.get("global_video_id")
    _parse_persons(cas, cursor, video_id, context)
