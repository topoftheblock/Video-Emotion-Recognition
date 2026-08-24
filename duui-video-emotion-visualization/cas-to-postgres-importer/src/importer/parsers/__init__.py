"""
Parsers package: one module per CAS/DB entity family.

Every module exposes a `parse(cas, cursor, context)` function with an
identical signature, where `context` is a plain dict shared across all
parsers for the current CAS (e.g. it carries `global_video_id` once
the video parser has resolved it).

No step gets the connection itself: the whole import is one
transaction owned by pipeline.py, which commits once every step has
run, so a step that could commit or roll back on its own would only be
a way to break that guarantee.

`PARSE_STEPS` defines the order in which parsers must run -- this
matters for two reasons: later steps depend on
`context["global_video_id"]`/the face-voice-person maps being set by
earlier steps, and the real Postgres schema has FK constraints (e.g.
`segments.person_id -> persons.person_id`) that fail outright if a
referenced row hasn't been inserted yet. `person` therefore runs right
after `video`/`model`, before anything that can reference a person.

Every step here reads the CAS and writes what it found. Nothing in this
package derives data the CAS doesn't contain: cross-video person
identity (`global_persons`/`persons.global_person_id`) used to be a
step in this list, but it is corpus-wide rather than per-file, so it
now lives in its own container and is run explicitly -- see
global-identity-linker/. This importer never writes those
two columns at all.
"""

from . import (
    detection,
    embedding,
    emotion,
    model,
    person,
    presence,
    segment,
    text_emotion,
    token,
    video,
)

PARSE_STEPS = [
    video,  # must run first: resolves context["global_video_id"]
    model,
    person,  # video-local Person rows; builds face/voice -> person maps.
    # Must run before anything with a person_id FK (segment, embedding,
    # presence, detection, emotion all reference persons.person_id).
    segment,
    token,
    embedding,  # Face + Voice embeddings (uses the maps built by `person`)
    presence,  # uses the maps built by `person`
    detection,  # Face + Person detections (uses the maps built by `person`)
    emotion,  # video/audio BaseEmotion + EmotionScore
    text_emotion,  # text-based GoEmotions -> BaseEmotion + EmotionScore
]

__all__ = ["PARSE_STEPS"]
