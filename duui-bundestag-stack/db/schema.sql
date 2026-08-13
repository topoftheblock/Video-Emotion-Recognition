-- Enable the vector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Core Infrastructure & Models
CREATE TABLE videos (
    video_id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    duration DOUBLE PRECISION,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fps DOUBLE PRECISION,
    width INT,
    height INT
);

CREATE TABLE models (
    model_id BIGSERIAL PRIMARY KEY,
    name TEXT,
    version TEXT,
    source TEXT
);

-- 2. Identity Layer
CREATE TABLE global_persons (
    global_person_id BIGSERIAL PRIMARY KEY,
    real_name TEXT
);

CREATE TABLE persons (
    person_id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    global_person_id BIGINT REFERENCES global_persons(global_person_id) ON DELETE SET NULL,
    clip_label TEXT,
    match_score DOUBLE PRECISION
);

-- 3. Text & Segments Layer
CREATE TABLE segments (
    segment_id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    kind TEXT CHECK (kind IN ('shot', 'sentence')),
    seg_index INT,
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    begin_offset INT,
    end_offset INT,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE SET NULL
);

CREATE TABLE linguistic_tokens (
    token_id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    segment_id BIGINT REFERENCES segments(segment_id) ON DELETE CASCADE,
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    begin_offset INT,
    end_offset INT,
    word TEXT,
    pos_tag TEXT,
    ner_label TEXT
);

-- 4. Embeddings, Presence & Detections Layer
CREATE TABLE face_embeddings (
    embedding_id BIGSERIAL PRIMARY KEY,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE CASCADE,
    model_id BIGINT REFERENCES models(model_id) ON DELETE SET NULL,
    embedding vector(512)
);

CREATE TABLE voice_embeddings (
    embedding_id BIGSERIAL PRIMARY KEY,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE CASCADE,
    model_id BIGINT REFERENCES models(model_id) ON DELETE SET NULL,
    embedding vector(192)
);

-- HNSW, cosine distance (`<=>`) -- the doc in data_schema_with_types.md
-- has always described these embeddings as "pgvector HNSW-Index:
-- cosine", but the index itself was never actually created until now.
-- Drives both the cross-video global-person linking step
-- (importer/duui_parser/parsers/global_identity.py) and any similarity search
-- the NL->SQL query agent writes. `vector_cosine_ops` matches the
-- `<=>` operator used everywhere else in this codebase.
CREATE INDEX IF NOT EXISTS face_embeddings_embedding_hnsw_idx
    ON face_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS voice_embeddings_embedding_hnsw_idx
    ON voice_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE presences (
    presence_id BIGSERIAL PRIMARY KEY,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE CASCADE,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    modality TEXT CHECK (modality IN ('visible', 'speech')),
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    begin_offset INT,
    end_offset INT
);

CREATE TABLE face_detections (
    detection_id BIGSERIAL PRIMARY KEY,
    presence_id BIGINT REFERENCES presences(presence_id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE CASCADE,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    frame_index INT,
    t_time DOUBLE PRECISION,
    x REAL,
    y REAL,
    w REAL,
    h REAL,
    detection_score DOUBLE PRECISION
);

CREATE TABLE person_detections (
    detection_id BIGSERIAL PRIMARY KEY,
    presence_id BIGINT REFERENCES presences(presence_id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE CASCADE,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    frame_index INT,
    t_time DOUBLE PRECISION,
    x REAL,
    y REAL,
    w REAL,
    h REAL,
    detection_score DOUBLE PRECISION
);

-- 5. Emotion Layer
CREATE TABLE base_emotions (
    emotion_id BIGSERIAL PRIMARY KEY,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE CASCADE,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    modality TEXT CHECK (modality IN ('audio', 'video', 'text')),
    granularity TEXT CHECK (granularity IN ('frame', 'segment', 'sentence', 'shot')),
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    begin_offset INT,
    end_offset INT,
    frame_index INT,
    x REAL,
    y REAL,
    w REAL,
    h REAL,
    valence DOUBLE PRECISION,
    arousal DOUBLE PRECISION,
    dominance DOUBLE PRECISION,
    dominant_label TEXT
);

CREATE TABLE emotion_scores (
    score_id BIGSERIAL PRIMARY KEY,
    emotion_id BIGINT REFERENCES base_emotions(emotion_id) ON DELETE CASCADE,
    label TEXT,
    score DOUBLE PRECISION,
    UNIQUE (emotion_id, label)
);

-- 6. Supporting indexes
-- Not required for correctness (every FK already has an implicit
-- index on its own PK side), but these back the join/filter patterns
-- the per-video post-processing step runs on every import
-- (importer/duui_parser/parsers/global_identity.py) and that the
-- NL->SQL query agent tends to write.
CREATE INDEX IF NOT EXISTS base_emotions_video_modality_idx
    ON base_emotions (video_id, modality);
CREATE INDEX IF NOT EXISTS segments_video_kind_idx
    ON segments (video_id, kind);
CREATE INDEX IF NOT EXISTS face_embeddings_person_idx
    ON face_embeddings (person_id);
CREATE INDEX IF NOT EXISTS voice_embeddings_person_idx
    ON voice_embeddings (person_id);