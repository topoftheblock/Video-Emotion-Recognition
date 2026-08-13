"""
Resolves Person <-> FaceIdentity <-> VoiceIdentity links.

Some pipelines connect these with direct FeatureStructure references
(`FaceIdentity.person`, `VoiceIdentity.person`). Others -- including
the real Bundestag video-emotion CAS this was validated against --
only encode the link as a string on `identity:Person.label`, e.g.:

    label="voice:SPEAKER_00|face:face_7|score:0.83"

with `FaceIdentity.faceId` / `VoiceIdentity.voiceId` carrying the
matching string keys ("face_7", "SPEAKER_00"). The functions here
support both patterns: a direct reference is tried first, then a
lookup against the face_id/voice_id -> person_id maps built while
parsing identity:Person (see parsers/person.py), which are stored on
the shared pipeline `context` dict under "face_id_to_person_id" and
"voice_id_to_person_id".
"""

from .typesystem import get_xmi_id


def parse_person_label(label):
    """
    Parse a `key:value|key:value|...` label string into a dict, e.g.
    "voice:SPEAKER_00|face:face_7|score:0.83" ->
    {"voice": "SPEAKER_00", "face": "face_7", "score": 0.83}.

    Malformed segments are skipped rather than raising, since this
    label format isn't governed by the typesystem and may vary.
    """
    result = {}
    if not label:
        return result

    for part in label.split("|"):
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "score":
            try:
                value = float(value)
            except ValueError:
                continue
        result[key] = value

    return result


def resolve_person_id_via_face_fs(face_identity_fs, context):
    """
    Resolve a Person row's id from a FaceIdentity feature structure.

    Tries a direct `.person` reference first; falls back to matching
    `.faceId` against context["face_id_to_person_id"].
    """
    if face_identity_fs is None:
        return None

    direct_person = getattr(face_identity_fs, "person", None)
    if direct_person is not None:
        return get_xmi_id(direct_person)

    face_id = getattr(face_identity_fs, "faceId", None)
    return context.get("face_id_to_person_id", {}).get(face_id)


def resolve_person_id_via_voice_fs(voice_identity_fs, context):
    """
    Resolve a Person row's id from a VoiceIdentity feature structure.

    Tries a direct `.person` reference first; falls back to matching
    `.voiceId` against context["voice_id_to_person_id"].
    """
    if voice_identity_fs is None:
        return None

    direct_person = getattr(voice_identity_fs, "person", None)
    if direct_person is not None:
        return get_xmi_id(direct_person)

    voice_id = getattr(voice_identity_fs, "voiceId", None)
    return context.get("voice_id_to_person_id", {}).get(voice_id)
