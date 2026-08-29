CREATE EXTENSION IF NOT EXISTS vector;

-- Read before adding a table: everything imported from a CAS is keyed by
-- (video_id, <the CAS's own xmi:id>), never by the xmi:id alone. An xmi:id is
-- unique within one document and means nothing across documents, so the same id
-- names different things in different videos.
--
-- `models` and `global_persons` are the two deliberate exceptions: both are
-- corpus-wide and neither takes its id from a CAS.
--
-- See docs/database.md#conventions.

-- 1. Core Infrastructure & Models
CREATE TABLE videos (
    video_id BIGSERIAL PRIMARY KEY,
    -- The importer upserts on this, so a video re-imported any number of
    -- times keeps one row. It is also the join key to the video store: the
    -- webapp plays `<DUUI_VIDEO_DIR>/<filename>`.
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
    audio_video_match_score DOUBLE PRECISION,
    global_person_match_score DOUBLE PRECISION,
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
    -- Nullable because the upstream annotation carries the link only
    -- sometimes.
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
    embedding VECTOR(512),
    PRIMARY KEY (video_id, embedding_id),
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE CASCADE
);

CREATE TABLE voice_embeddings (
    video_id BIGINT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    embedding_id BIGINT NOT NULL,
    person_id BIGINT,
    model_id BIGINT REFERENCES models(model_id) ON DELETE SET NULL,
    embedding VECTOR(192),
    PRIMARY KEY (video_id, embedding_id),
    FOREIGN KEY (video_id, person_id) REFERENCES persons(video_id, person_id)
        ON DELETE CASCADE
);

-- HNSW on cosine distance. `vector_cosine_ops` is the operator class for
-- `<=>`, which is what identity linking compares centroids with
-- (global-identity-linker/src/identity/linking.py) and what any similarity
-- search the Ask panel generates will use.
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
    -- Often NULL, in every modality: a reading the upstream pipeline could
    -- not attribute to a person still belongs to the video.
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
-- Not required for correctness. These back the filters identity linking runs
-- over the whole corpus (global-identity-linker/src/identity/linking.py) and
-- the ones the Ask panel's generated SQL tends to use.
CREATE INDEX IF NOT EXISTS base_emotions_video_modality_idx
    ON base_emotions (video_id, modality);
CREATE INDEX IF NOT EXISTS segments_video_kind_idx
    ON segments (video_id, kind);
CREATE INDEX IF NOT EXISTS face_embeddings_person_idx
    ON face_embeddings (video_id, person_id);
CREATE INDEX IF NOT EXISTS voice_embeddings_person_idx
    ON voice_embeddings (video_id, person_id);

-- The referencing side of each composite foreign key. Postgres indexes the
-- referenced side automatically, not this one, so without these a cascade
-- deleting by person or presence scans. `--on-existing replace` deletes a
-- whole video's subtree on every re-import, which is when that matters.
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
-- One row per job run, so the webapp can report that an import is running and
-- how far it has got, rather than leaving an empty video list ambiguous.
--
-- This file runs only when the data directory is created empty, so an
-- already-populated deployment never sees it. The same DDL is therefore
-- repeated as CREATE TABLE IF NOT EXISTS in the three services that write or
-- read the table. The four are identical apart from the statement terminator,
-- which only this file needs; keep them so:
--   cas-to-postgres-importer/src/importer/job_runs.py
--   global-identity-linker/src/identity/job_runs.py
--   webapp/src/backend/queries/jobs.py
--
-- fillfactor leaves free space on each page for the heartbeat UPDATEs, which
-- rewrite one row roughly once a second for the length of a run
-- (MIN_WRITE_INTERVAL in job_runs.py). With room on the page those updates stay
-- HOT and leave no dead tuple or new index entry behind.
CREATE TABLE IF NOT EXISTS job_runs (
    job_run_id BIGSERIAL PRIMARY KEY,
    job TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT,
    progress_current INT,
    progress_total INT,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
) WITH (fillfactor = 70);

CREATE INDEX IF NOT EXISTS job_runs_running_idx
    ON job_runs (job, started_at DESC);
