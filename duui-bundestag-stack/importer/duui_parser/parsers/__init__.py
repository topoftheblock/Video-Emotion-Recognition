"""
Parsers package: one module per CAS/DB entity family.

Every module exposes a `parse(cas, cursor, conn, context)` function
with an identical signature, where `context` is a plain dict shared
across all parsers for the current CAS (e.g. it carries
`global_video_id` once the video parser has resolved it).

`PARSE_STEPS` defines the order in which parsers must run -- this
matters for two reasons: later steps depend on
`context["global_video_id"]`/the face-voice-person maps being set by
earlier steps, and the real Postgres schema has FK constraints (e.g.
`segments.person_id -> persons.person_id`) that fail outright if a
referenced row hasn't been inserted yet. `person` therefore runs right
after `video`/`model`, before anything that can reference a person.
"""

from . import (
    video,
    model,
    person,
    segment,
    token,
    embedding,
    global_identity,
    presence,
    detection,
    emotion,
    text_emotion,
    emotion_fusion,
    nlp_enrichment,
)

PARSE_STEPS = [
    video,          # must run first: resolves context["global_video_id"]
    model,
    person,         # includes GlobalPerson + Person; builds face/voice -> person maps.
                    # Must run before anything with a person_id FK (segment, embedding,
                    # presence, detection, emotion all reference persons.person_id).
    segment,
    token,
    embedding,      # Face + Voice embeddings (uses the maps built by `person`)
    global_identity, # cross-video person linking -- needs this video's persons
                    # (person) + embeddings (embedding) already inserted, and reads
                    # every other already-imported video's embeddings via pgvector.
    presence,       # uses the maps built by `person`
    detection,      # Face + Person detections (uses the maps built by `person`)
    emotion,        # video/audio BaseEmotion, EmotionScore, FusedEmotion, references
    text_emotion,   # text-based GoEmotions -> BaseEmotion + EmotionScore
    emotion_fusion, # multimodal fusion per sentence -- must run last: needs every
                    # modality's base_emotions rows for this video already inserted
    nlp_enrichment, # POS/NER backfill onto linguistic_tokens -- only needs segment/token,
                    # placed last alongside emotion_fusion since order doesn't matter for it
]

__all__ = ["PARSE_STEPS"]
