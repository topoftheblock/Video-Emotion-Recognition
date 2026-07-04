"""
Parsers package: one module per CAS/DB entity family.

Every module exposes a `parse(cas, cursor, conn, context)` function
with an identical signature, where `context` is a plain dict shared
across all parsers for the current CAS (e.g. it carries
`global_video_id` once the video parser has resolved it).

`PARSE_STEPS` defines the order in which parsers must run --
this matters because later steps (Segment, Person, Presence, ...)
depend on `context["global_video_id"]` being set by the video step.
"""

from . import (
    video,
    model,
    segment,
    token,
    person,
    embedding,
    presence,
    detection,
    emotion,
    text_emotion,
)

PARSE_STEPS = [
    video,          # must run first: resolves context["global_video_id"]
    model,
    segment,
    token,
    person,         # includes GlobalPerson + Person; builds face/voice -> person maps
    embedding,      # Face + Voice embeddings (uses the maps built by `person`)
    presence,       # uses the maps built by `person`
    detection,      # Face + Person detections (uses the maps built by `person`)
    emotion,        # video/audio BaseEmotion, EmotionScore, FusedEmotion, references
    text_emotion,   # text-based GoEmotions -> BaseEmotion + EmotionScore
]

__all__ = ["PARSE_STEPS"]
