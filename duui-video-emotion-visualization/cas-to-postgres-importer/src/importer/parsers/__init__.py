"""One parser module per family of CAS annotations and database rows.

Every module exposes a `parse(cas, cursor, context)` with an identical
signature. The context is a plain dict shared across all parsers for
the current CAS: it carries `global_video_id` once the video step has
resolved it, and the person lookup maps once the person step has built
them.

No step is given the connection. The whole import is one transaction
owned by `pipeline.py`, which commits after every step has run, so a
step able to commit or roll back on its own would only be a way to
break that guarantee.

`PARSE_STEPS` fixes the order, which matters twice over: later steps
read what earlier ones put in the context, and the schema's foreign
keys fail outright if a referenced row is not yet inserted. `person`
therefore runs directly after `video` and `model`, ahead of anything
that can reference a person.

Every step reads the CAS and writes what it found. Nothing here derives
data the CAS does not contain. Linking people across videos was once a
step in this list, but it is corpus-wide rather than per-file, so it
now lives in `global-identity-linker/` and is run explicitly. This
importer never writes `global_persons` or `persons.global_person_id`.
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
