# Emotion Recognition in DUUI

Multimodal emotion and identity recognition over recorded video (built
against German Bundestag session footage): a video is run through a
[DUUI](https://github.com/texttechnologylab/DockerUnifiedUIMAInterface)
pipeline that transcribes speech, diarizes speakers, and scores
emotion from the **text**, **audio**, and **video** modalities
independently, plus resolves **who** is on screen. The result is
parsed into Postgres and explored in a web viewer with synced
subtitles, per-modality emotion readouts, face/person bounding boxes,
and a natural-language query agent.

<p align="center">
  <img src="duui_bundestag_pipeline/docs/screenshots/overview.png" alt="Web viewer: video with face bounding box + emotion label, live subtitle, voice/people/on-screen panels" width="760">
</p>

More screenshots, a full use-case list for the query agent, and how
its natural-language-to-SQL loop actually works are in
[`duui_bundestag_pipeline/README.md`](duui_bundestag_pipeline/README.md#natural-language-query-agent).

## How it fits together

```
                    ┌─────────────────────────────────────────────┐
                    │   DUUI orchestrator (src/, pom.xml, Java)    │
                    │   DUUIComposer wires the components below    │
                    │   into one pipeline over a UIMA CAS           │
                    └───────────────────┬───────────────────────────┘
                                        │
      video (_InitialView)             │  transcript / audio / emotion views
      ┌─────────────────────────────────┼─────────────────────────────────┐
      │                                 │                                 │
      ▼                                 ▼                                 ▼
 WhisperX                    duui-extract-audio-to-view      video-phase2-docker
 (remote transcription       + duui-audio-speaker-diarization  (face detection +
  service)                   + duui-audio-sentence-merger       video-modality
      │                       (pyannote speaker turns ->         emotion -- WIP,
      ▼                        per-sentence audio windows)       not finished)
   spaCy (German NLP:               │
   sentence/token)                  ▼
      │                     audiodocker / whisper-emotion-app
      ▼                     (audio-modality emotion, SER)
 German-Emotions
 (text-modality emotion)
      │
      ▼
        ─────────────  CAS XMI output  ─────────────
                              │
                              ▼
                duui_bundestag_pipeline/  (Python)
        parses the CAS into Postgres (+ pgvector for
        face/voice embeddings), then serves a web
        viewer + an LLM-backed natural-language query
        agent over the results
```

The Java side (`src/`, driven by `pom.xml`) is the actual pipeline
definition -- it's what you'd run to process a new video end-to-end.
Everything under `duui_bundestag_pipeline/` is downstream of that: it
consumes whatever CAS XMI the Java pipeline produced and is where the
finished, dockerized, actively-maintained part of this project lives
(database, web viewer, query agent). **If you just want to run
something, start there** -- it has its own detailed README covering
setup, Docker, and the query agent.

## Repository layout

| Path | What it is |
|---|---|
| [`duui_bundestag_pipeline/`](duui_bundestag_pipeline/README.md) | **Start here.** CAS-to-Postgres parser, web viewer (subtitles/emotions/bounding boxes in sync with playback), and the natural-language query agent. Fully dockerized (`docker compose up`), tested end-to-end. |
| `src/`, `pom.xml` | The DUUI pipeline itself (Java, Maven, `Multimodal_Emotion` artifact) -- `VideoPipe.java` is the `DUUIComposer` definition that chains every component below over a video's UIMA CAS. |
| [`audio_text_pipeline/`](audio_text_pipeline/readme.md) | Notes on the DUUI multimodal architecture (CAS views, the Lua/HTTP bridge to Python components) plus an alternate audio+text-only pipeline runner. |
| [`duui-extract-audio-to-view/`](duui-extract-audio-to-view/readme.md) | DUUI component: pulls the audio track out of a video view via `ffmpeg`, writes it into its own CAS view. |
| [`duui-audio-speaker-diarization/`](duui-audio-speaker-diarization/readme.md) | DUUI component: "who spoke when" via `pyannote.audio` (gated HuggingFace model, needs a token). |
| `duui-audio-sentence-merger/` | DUUI component: merges per-token audio timing + speaker IDs into one time window per sentence. |
| `audiodocker/` | DUUI component behind `whisper-emotion-app` in `VideoPipe.java` -- audio-modality emotion (speech emotion recognition). |
| `video-phase2-docker/` | DUUI component for video-modality emotion/face detection -- **not finished** (per its own commit history); the video-modality data already in `duui_bundestag_pipeline`'s sample CAS came from elsewhere, not this component yet. |
| `CAS_to_DB/` | Earlier prototype of what `duui_bundestag_pipeline/` became (placeholder DB credentials, a stub sample-video player). Superseded -- kept for history, not actively maintained. |
| `references/` | Background material, not runnable code: DUUI/vision-identity notes (`vision-id/`), earlier pipeline sketches (`nlp/`), and slides/docs (`docs/`). |

## Tech stack

- **Orchestration**: Java + Maven, [DockerUnifiedUIMAInterface](https://github.com/texttechnologylab/DockerUnifiedUIMAInterface) (DUUI) over Apache UIMA -- each pipeline stage is either a Docker component, a remote HTTP component, or a plain UIMA analysis engine, composed by `DUUIComposer`.
- **Pipeline components**: Python (FastAPI + a Lua communication-layer script per DUUI convention), wrapping WhisperX, spaCy, HuggingFace transformer emotion models, and `pyannote.audio`.
- **Downstream (`duui_bundestag_pipeline/`)**: Python (`dkpro-cassis` for CAS parsing, FastAPI web viewer), PostgreSQL + `pgvector`, Docker/Docker Compose, vanilla HTML/CSS/JS frontend, an OpenAI-compatible LLM (Qwen3-VL via a university-hosted gateway) for the natural-language query agent.

## Where the actual data comes from

CAS XMI files are the handoff point between the two halves of this
project: the Java/DUUI side produces them by running a video through
the full pipeline; `duui_bundestag_pipeline/` only ever consumes them
(see that project's README for the exact schema and typesystem
requirements). The sample video(s) in `duui_bundestag_pipeline/cas/`
are committed to the repo, but the `.xmi` CAS files parsed from them
are not (see its `.gitignore`) -- bring your own, or re-run the Java
pipeline against a video to produce one.
