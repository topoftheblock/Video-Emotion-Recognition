-- Enable the vector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Core Infrastructure & NLP
CREATE TABLE videos (
    video_id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    duration DOUBLE PRECISION,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE linguistic_tokens (
    token_id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    begin_offset INT,
    end_offset INT,
    word TEXT,
    pos_tag TEXT,
    ner_label TEXT
);

-- 2. Identity & Presence Layer
CREATE TABLE global_persons (
    global_person_id BIGSERIAL PRIMARY KEY,
    real_name TEXT
);

CREATE TABLE persons (
    person_id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    global_person_id BIGINT REFERENCES global_persons(global_person_id) ON DELETE SET NULL,
    clip_label TEXT
);

CREATE TABLE biometric_embeddings (
    embedding_id BIGSERIAL PRIMARY KEY,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE CASCADE,
    modality TEXT CHECK (modality IN ('face', 'voice')),
    embedding vector(512) -- ArcFace / ResNet-50 dimension size
);

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
    h REAL
);

-- 3. Emotion Layer
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
    score DOUBLE PRECISION
);

CREATE TABLE fused_emotions (
    fused_id BIGSERIAL PRIMARY KEY,
    video_id BIGINT REFERENCES videos(video_id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES persons(person_id) ON DELETE SET NULL,
    fusion_method TEXT,
    target_modality TEXT CHECK (target_modality IN ('multimodal', 'video-aggregated', 'text-aggregated')),
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    valence DOUBLE PRECISION,
    arousal DOUBLE PRECISION,
    dominant_label TEXT
);

CREATE TABLE emotion_fusion_references (
    fused_id BIGINT REFERENCES fused_emotions(fused_id) ON DELETE CASCADE,
    source_emotion_id BIGINT REFERENCES base_emotions(emotion_id) ON DELETE CASCADE,
    PRIMARY KEY (fused_id, source_emotion_id)
);