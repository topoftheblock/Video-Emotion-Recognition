"""Resolving the links between Person, FaceIdentity and VoiceIdentity.

Some pipelines connect these with direct feature-structure references
(`FaceIdentity.person`, `VoiceIdentity.person`). Others — including the
real Bundestag CAS this was validated against — encode the link only as
a string on `identity:Person.label`:

    label="voice:SPEAKER_00|face:face_7|score:0.83"

with `FaceIdentity.faceId` and `VoiceIdentity.voiceId` carrying the
matching keys ("face_7", "SPEAKER_00").

Both patterns are supported: a direct reference is tried first, then a
lookup against the face-id and voice-id maps built while parsing
`identity:Person` (see `parsers/person.py`). Those maps live on the
shared pipeline context under "face_id_to_person_id" and
"voice_id_to_person_id".
"""

from typing import Any

from cassis.typesystem import FeatureStructure

from .typesystem import get_xmi_id


def parse_person_label(label: str | None) -> dict[str, Any]:
    """Parse a `key:value|key:value|...` label into a dict.

    So "voice:SPEAKER_00|face:face_7|score:0.83" becomes
    `{"voice": "SPEAKER_00", "face": "face_7", "score": 0.83}`, with
    "score" converted to a float.

    Malformed segments are skipped rather than raising: this label
    format is not governed by the typesystem, so it may vary.

    Args:
        label: The raw label string, or None.

    Returns:
        The parsed pairs; empty when there is nothing usable.
    """
    result: dict[str, Any] = {}
    if not label:
        return result

    for part in label.split("|"):
        if ":" not in part:
            continue
        key, _, raw = part.partition(":")
        key = key.strip()
        value: Any = raw.strip()
        if key == "score":
            try:
                value = float(value)
            except ValueError:
                continue
        result[key] = value

    return result


def resolve_person_id_via_face_fs(
    face_identity_fs: FeatureStructure | None, context: dict[str, Any]
) -> int | None:
    """Resolve a person's id from a FaceIdentity structure.

    Tries a direct `.person` reference first, then falls back to
    matching `.faceId` against `context["face_id_to_person_id"]`.

    Args:
        face_identity_fs: The FaceIdentity structure, or None.
        context: The shared pipeline context.

    Returns:
        The person's `xmi:id`, or None if it cannot be resolved.
    """
    if face_identity_fs is None:
        return None

    direct_person = getattr(face_identity_fs, "person", None)
    if direct_person is not None:
        return get_xmi_id(direct_person)

    face_id = getattr(face_identity_fs, "faceId", None)
    return context.get("face_id_to_person_id", {}).get(face_id)


def resolve_person_id_via_voice_fs(
    voice_identity_fs: FeatureStructure | None, context: dict[str, Any]
) -> int | None:
    """Resolve a person's id from a VoiceIdentity structure.

    Tries a direct `.person` reference first, then falls back to
    matching `.voiceId` against `context["voice_id_to_person_id"]`.

    Args:
        voice_identity_fs: The VoiceIdentity structure, or None.
        context: The shared pipeline context.

    Returns:
        The person's `xmi:id`, or None if it cannot be resolved.
    """
    if voice_identity_fs is None:
        return None

    direct_person = getattr(voice_identity_fs, "person", None)
    if direct_person is not None:
        return get_xmi_id(direct_person)

    voice_id = getattr(voice_identity_fs, "voiceId", None)
    return context.get("voice_id_to_person_id", {}).get(voice_id)
