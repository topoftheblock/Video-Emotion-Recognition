-- Enable the vector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Identity note (read before adding a table)
-- ------------------------------------------
-- Everything imported from a CAS is keyed by (video_id, <the CAS's own
-- xmi:id>), never by the xmi:id alone. XMI ids are a per-document
-- counter: every file restarts at 1, so they are unique *within* a
-- document and meaningless across documents. Keying on them alone
-- silently merged whole videos into one another -- nine files landed
-- on a single `videos` row because each declared its DocumentMetaData
-- at xmi:id 3, and 4,420 of 42,939 emotion ids collided between files,
-- each one either dropped or overwritten with another video's reading.
--
-- `video_id` is therefore a real surrogate (BIGSERIAL), and `videos`
-- is keyed for the importer by `filename`, which is the one identifier
-- that is stable per video and already the join key to the video store
-- the webapp plays from.
--
-- Two exceptions, both deliberate:
--   * `models` is corpus-global (the same face model processes every
--     video), so it uses its natural key instead of being duplicated
--     per video.
--   * `global_persons` is corpus-wide by definition and its ids are
--     assigned by the database, not by any CAS.

-- 1. Core Infrastructure & Models
CREATE TABLE videos (
    video_id BIGSERIAL PRIMARY KEY,
    -- The importer upserts on this: one row per video file, however
    -- many times it is imported. It is also how the webapp finds the
    -- playable file in the video store, so two different recordings
    -- sharing a filename would already be indistinguishable there.
    filename TEXT NOT NULL UNIQUE,
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
    source TEXT,
    -- NULLS NOT DISTINCT: a model annotation that carries no version or
    -- source must still match the row it wrote last time, rather than
    -- inserting a new one on every import (Postgres treats NULLs in a
    -- unique constraint as distinct by default).
    UNIQUE NULLS NOT DISTINCT (name, version, source)
);

-- 2. Identity Layer
CREATE TABLE global_persons (
    global_person_id BIGSERIAL PRIMARY KEY,
    real_name TEXT
);

CREATE TABLE persons (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL,
    global_person_id BIGINT REFERENCES global_persons(global_person_id) ON DELETE SET NULL,
    clip_label TEXT,
    match_score DOUBLE PRECISION,
    PRIMARY KEY (video_id, person_id)
);

-- 3. Text & Segments Layer
CREATE TABLE segments (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    segment_id BIGINT NOT NULL,
    kind TEXT CHECK (kind IN ('shot', 'sentence')),
    seg_index INT,
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    begin_offset INT,
    end_offset INT,
    person_id BIGINT,
    PRIMARY KEY (video_id, segment_id),
    -- SET NULL names the column explicitly: video_id is half of this
    -- row's own identity and cannot be nulled, so only the speaker
    -- reference is cleared. A segment with no person_id is a normal
    -- state (a shot has no speaker), which is also why this FK is
    -- MATCH SIMPLE -- a NULL person_id leaves it unenforced.
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE SET NULL (person_id)
);

CREATE TABLE linguistic_tokens (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    token_id BIGINT NOT NULL,
    segment_id BIGINT,
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    begin_offset INT,
    end_offset INT,
    word TEXT,
    pos_tag TEXT,
    ner_label TEXT,
    PRIMARY KEY (video_id, token_id),
    -- segment_id is not always populated on the source annotation
    -- (see media/pipeline notes on time-range matching), hence
    -- nullable rather than NOT NULL.
    FOREIGN KEY (video_id, segment_id) REFERENCES segments(video_id, segment_id)
        ON DELETE CASCADE
);

-- 4. Embeddings, Presence & Detections Layer
CREATE TABLE face_embeddings (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    embedding_id BIGINT NOT NULL,
    person_id BIGINT,
    -- Single-column FK: models are corpus-global, not per video.
    model_id BIGINT REFERENCES models(model_id) ON DELETE SET NULL,
    embedding vector(512),
    PRIMARY KEY (video_id, embedding_id),
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE CASCADE
);

CREATE TABLE voice_embeddings (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    embedding_id BIGINT NOT NULL,
    person_id BIGINT,
    model_id BIGINT REFERENCES models(model_id) ON DELETE SET NULL,
    embedding vector(192),
    PRIMARY KEY (video_id, embedding_id),
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE CASCADE
);

-- HNSW, cosine distance (`<=>`) -- the doc in data_schema_with_types.md
-- has always described these embeddings as "pgvector HNSW-Index:
-- cosine", but the index itself was never actually created until now.
-- Drives both the cross-video global-person linking job
-- (duui-video-emotion-global-identity/src/identity/linking.py)
-- and any similarity search the NL->SQL query agent writes.
-- `vector_cosine_ops` matches the
-- `<=>` operator used everywhere else in this codebase.
CREATE INDEX IF NOT EXISTS face_embeddings_embedding_hnsw_idx
    ON face_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS voice_embeddings_embedding_hnsw_idx
    ON voice_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE presences (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    presence_id BIGINT NOT NULL,
    person_id BIGINT,
    modality TEXT CHECK (modality IN ('visible', 'speech')),
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    begin_offset INT,
    end_offset INT,
    PRIMARY KEY (video_id, presence_id),
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE CASCADE
);

CREATE TABLE face_detections (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    detection_id BIGINT NOT NULL,
    presence_id BIGINT,
    person_id BIGINT,
    frame_index INT,
    t_time DOUBLE PRECISION,
    x REAL,
    y REAL,
    w REAL,
    h REAL,
    detection_score DOUBLE PRECISION,
    PRIMARY KEY (video_id, detection_id),
    FOREIGN KEY (video_id, presence_id) REFERENCES presences(video_id, presence_id)
        ON DELETE CASCADE,
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE CASCADE
);

CREATE TABLE person_detections (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    detection_id BIGINT NOT NULL,
    presence_id BIGINT,
    person_id BIGINT,
    frame_index INT,
    t_time DOUBLE PRECISION,
    x REAL,
    y REAL,
    w REAL,
    h REAL,
    detection_score DOUBLE PRECISION,
    PRIMARY KEY (video_id, detection_id),
    FOREIGN KEY (video_id, presence_id) REFERENCES presences(video_id, presence_id)
        ON DELETE CASCADE,
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE CASCADE
);

-- 5. Emotion Layer
CREATE TABLE base_emotions (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    emotion_id BIGINT NOT NULL,
    -- Regularly NULL: video-modality frames the importer could not
    -- attribute to anyone still belong to the video.
    person_id BIGINT,
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
    dominant_label TEXT,
    PRIMARY KEY (video_id, emotion_id),
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE CASCADE
);

CREATE TABLE emotion_scores (
    score_id BIGSERIAL PRIMARY KEY,
    video_id BIGINT NOT NULL,
    emotion_id BIGINT NOT NULL,
    label TEXT,
    score DOUBLE PRECISION,
    UNIQUE (video_id, emotion_id, label),
    FOREIGN KEY (video_id, emotion_id) REFERENCES base_emotions(video_id, emotion_id)
        ON DELETE CASCADE
);

-- 6. Supporting indexes
-- Not required for correctness (every FK already has an implicit
-- index on its own PK side), but these back the join/filter patterns
-- the cross-video identity job runs over the whole corpus
-- (duui-video-emotion-global-identity/src/identity/linking.py)
-- and that the NL->SQL query agent tends to write.
CREATE INDEX IF NOT EXISTS base_emotions_video_modality_idx
    ON base_emotions (video_id, modality);
CREATE INDEX IF NOT EXISTS segments_video_kind_idx
    ON segments (video_id, kind);
CREATE INDEX IF NOT EXISTS face_embeddings_person_idx
    ON face_embeddings (video_id, person_id);
CREATE INDEX IF NOT EXISTS voice_embeddings_person_idx
    ON voice_embeddings (video_id, person_id);

-- Referencing sides of the composite FKs. A composite PRIMARY KEY
-- indexes (video_id, own_id), which is no help to a cascade that
-- deletes by person or presence -- and `--on-existing replace` deletes
-- a whole video's subtree on every re-import, so these are the
-- difference between a delete that seeks and one that scans every
-- detection in the corpus.
CREATE INDEX IF NOT EXISTS segments_person_idx
    ON segments (video_id, person_id);
CREATE INDEX IF NOT EXISTS linguistic_tokens_segment_idx
    ON linguistic_tokens (video_id, segment_id);
CREATE INDEX IF NOT EXISTS presences_person_idx
    ON presences (video_id, person_id);
CREATE INDEX IF NOT EXISTS face_detections_presence_idx
    ON face_detections (video_id, presence_id);
CREATE INDEX IF NOT EXISTS face_detections_person_idx
    ON face_detections (video_id, person_id);
CREATE INDEX IF NOT EXISTS person_detections_presence_idx
    ON person_detections (video_id, presence_id);
CREATE INDEX IF NOT EXISTS person_detections_person_idx
    ON person_detections (video_id, person_id);
CREATE INDEX IF NOT EXISTS base_emotions_person_idx
    ON base_emotions (video_id, person_id);

-- 7. Job status
-- One row per run of a long-running job (the importer, the
-- cross-video identity job), so the viewer can say "an import is
-- running" and how far along it is instead of leaving a user to guess
-- whether the empty dropdown is a bug or a job that hasn't finished.
--
-- This file only runs when the db volume is created empty, so an
-- already-populated deployment never sees it. The same DDL is
-- therefore repeated as CREATE TABLE IF NOT EXISTS in each service
-- that touches the table -- keep the four copies in step:
--   duui-video-emotion-cas-to-postgres/src/main/job_runs.py
--   duui-video-emotion-global-identity/src/identity/job_runs.py
--   duui-video-emotion-visualization-webapp/src/backend/queries/jobs.py
--
-- fillfactor leaves room on the page for the heartbeat UPDATEs, which
-- rewrite the same row once a second for the length of a run: with
-- space to spare they stay HOT (in-page) instead of leaving a dead
-- tuple and a new index entry behind every time.
CREATE TABLE IF NOT EXISTS job_runs (
    job_run_id BIGSERIAL PRIMARY KEY,
    job TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT,
    progress_current INT,
    progress_total INT,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
) WITH (fillfactor = 70);

CREATE INDEX IF NOT EXISTS job_runs_running_idx
    ON job_runs (job, started_at DESC);
