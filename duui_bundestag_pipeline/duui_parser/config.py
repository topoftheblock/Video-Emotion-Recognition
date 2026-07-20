"""
Central configuration for the DUUI CAS parser.

Keeping every path / credential / type-name in one place means the
rest of the codebase never hardcodes a UIMA type name or a DB
setting inline -- everything is imported from here.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv is optional -- if it's not installed, real environment
    # variables (export FOO=bar, or set by your process manager) still
    # work fine; only the convenience of a local .env file is lost.
    pass

# --- File locations -------------------------------------------------

XMI_FILE = os.environ.get("DUUI_XMI_FILE", "cas/full_2sek_with_person.xmi")

TYPESYSTEM_FILES = {
    "identity_emotion": os.environ.get(
        "DUUI_TS_IDENTITY_EMOTION", "typesystems/IdentityEmotionTypeSystem.xml"
    ),
    "multimodal_identity": os.environ.get(
        "DUUI_TS_MULTIMODAL_IDENTITY", "typesystems/MultimodalIdentityTypeSystem.xml"
    ),
    "emotion": os.environ.get("DUUI_TS_EMOTION", "typesystems/EmotionTypeSystem.xml"),
}

# --- Database ---------------------------------------------------------

# --- Natural-language query agent -------------------------------------
# Talks to an OpenAI-compatible chat-completions endpoint (this project
# uses a university-hosted Open WebUI/Ollama gateway serving Qwen3-VL,
# not Anthropic directly -- swap DUUI_QUERY_BASE_URL/DUUI_QUERY_MODEL to
# point at a different OpenAI-compatible provider if needed).

QUERY_AGENT_API_KEY = os.environ.get("DUUI_QUERY_API_KEY", "")
QUERY_AGENT_BASE_URL = os.environ.get(
    "DUUI_QUERY_BASE_URL", "https://lehre.llm.texttechnologylab.org/api"
)
QUERY_AGENT_MODEL = os.environ.get("DUUI_QUERY_MODEL", "gondor.qwen3-vl:32b")
QUERY_AGENT_MAX_ROWS = int(os.environ.get("DUUI_QUERY_MAX_ROWS", "500"))
QUERY_AGENT_STATEMENT_TIMEOUT_MS = int(
    os.environ.get("DUUI_QUERY_STATEMENT_TIMEOUT_MS", "8000")
)
QUERY_AGENT_MAX_TOOL_ITERATIONS = int(
    os.environ.get("DUUI_QUERY_MAX_TOOL_ITERATIONS", "6")
)

# --- Post-processing pipeline steps ------------------------------------
# These run automatically as part of every `python main.py` import (see
# duui_parser/parsers/__init__.py) -- each can be switched off
# independently for a faster import or a constrained environment
# without breaking the rest of the pipeline.

def _bool_env(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# Cross-video person identity (duui_parser/parsers/global_identity.py):
# after a video's face/voice embeddings are inserted, each new local
# person is matched via pgvector cosine distance against every other
# video's persons; a match below the threshold links both to the same
# global_persons row (creating one if neither side had one yet).
ENABLE_GLOBAL_PERSON_LINKING = _bool_env("DUUI_ENABLE_GLOBAL_PERSON_LINKING", True)
# Cosine distance (`<=>`, 0 = identical .. 2 = opposite) -- lower is
# stricter. 0.30 is a conservative starting point for ArcFace-style
# 512-dim face embeddings; retune against real cross-video duplicates
# before trusting this for anything beyond suggestions.
GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD = float(
    os.environ.get("DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD", "0.30")
)
GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD = float(
    os.environ.get("DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD", "0.35")
)

# Emotion fusion (duui_parser/parsers/emotion_fusion.py): computes one
# multimodal fused_emotions row per sentence from whichever of
# audio/video/text base_emotions are available for it.
ENABLE_EMOTION_FUSION = _bool_env("DUUI_ENABLE_EMOTION_FUSION", True)

# NLP enrichment (duui_parser/parsers/nlp_enrichment.py): runs spaCy
# POS/NER over each sentence's reconstructed text and backfills
# linguistic_tokens.pos_tag/ner_label, which the source CAS leaves
# empty. Off by default -- unlike the other two steps this pulls in a
# large model download (see requirements.txt), so it's opt-in.
ENABLE_NLP_ENRICHMENT = _bool_env("DUUI_ENABLE_NLP_ENRICHMENT", False)
SPACY_MODEL = os.environ.get("DUUI_SPACY_MODEL", "de_core_news_sm")

# --- Database ---------------------------------------------------------

DB_CONFIG = {
    "dbname": os.environ.get("DUUI_DB_NAME", "your_db"),
    "user": os.environ.get("DUUI_DB_USER", "your_user"),
    "password": os.environ.get("DUUI_DB_PASSWORD", "your_password"),
    "host": os.environ.get("DUUI_DB_HOST", "localhost"),
}

# --- UIMA type names ----------------------------------------------------
# Centralising these means a type-system rename only touches this file.

TYPES = {
    "multimedia_element": "org.texttechnologylab.annotation.type.MultimediaElement",
    "document_meta_data": "de.tudarmstadt.ukp.dkpro.core.api.metadata.type.DocumentMetaData",
    # NOTE: this lives under the `.model` subpackage, not directly under
    # `.annotation` -- confirmed against real DUUI-video-emotion output.
    # NOTE: canonical mapping doc (data_schema_with_types.md) specifies
    # the bare `annotation.MetaData` type here, not `.model.MetaData`.
    # Since `model.MetaData`/`model.HuggingfaceMetaData` both extend
    # this bare type (see INJECTED_FALLBACK_TYPES), selecting the bare
    # type already picks up every concrete subtype instance too --
    # cassis's select() includes descendants -- so this single type
    # name covers all real Model rows without a second select.
    "model_meta_data": "org.texttechnologylab.annotation.MetaData",
    "huggingface_meta_data": "org.texttechnologylab.annotation.model.HuggingfaceMetaData",
    "shot": "org.texttechnologylab.annotation.video.Shot",
    "speaker_sentence": "org.texttechnologylab.annotation.audio.SpeakerSentence",
    "speaker_segment": "org.texttechnologylab.annotation.audio.SpeakerSegment",
    "diarized_audio_token": "org.texttechnologylab.annotation.type.DiarizedAudioToken",
    "global_person": "org.texttechnologylab.annotation.identity.GlobalPerson",
    "person": "org.texttechnologylab.annotation.identity.Person",
    "face_identity": "org.texttechnologylab.annotation.identity.FaceIdentity",
    "voice_identity": "org.texttechnologylab.annotation.identity.VoiceIdentity",
    "embedding": "org.texttechnologylab.uima.type.Embedding",
    "person_track": "org.texttechnologylab.annotation.video.PersonTrack",
    "face_detection": "org.texttechnologylab.annotation.video.FaceDetection",
    "person_detection": "org.texttechnologylab.annotation.video.PersonDetection",
    "emotion": "org.texttechnologylab.annotation.emotion.Emotion",
    # Text-based GoEmotions analysis is a *different* type from the
    # per-frame video/audio Emotion above -- it lives directly under
    # `.annotation`, not `.annotation.emotion`.
    "goemotions_emotion": "org.texttechnologylab.annotation.Emotion",
    "annotation_comment": "org.texttechnologylab.annotation.AnnotationComment",
}

# Fallback type descriptions for types this parser depends on that are
# missing from the provided typesystem files entirely -- confirmed
# against the real Bundestag video-emotion typesystem files:
# `MultimediaElement`, `AudioToken`, the bare `MetaData`, and
# `Embedding` are all referenced (as a supertype or a feature's
# range/element type) but never actually defined in any of the three
# files. They evidently come from external/shared typesystem imports
# declared by name (e.g. `desc.type.TextTechnologyMultimedia`) that
# weren't included alongside the project-specific files.
#
# `MultimediaElement` matters most: it's the supertype of most
# time-bounded annotations in this pipeline (Shot, PersonTrack,
# Detection, SpeakerSegment, SpeakerSentence, Emotion), and those
# subtypes don't redeclare `timeStart`/`timeEnd` themselves -- they
# inherit them. Confirmed against the real CAS: those fields *are*
# present on real instances, so the fallback here must declare them or
# every subtype fails to load with an "unexpected keyword argument"
# error.
#
# The GoEmotions-style raw multi-label classification (a distinct
# `annotation.Emotion` + `AnnotationComment` pair, not the same type as
# the richer per-frame `annotation.emotion.Emotion` defined in the
# provided files) isn't part of these three files at all -- it
# apparently comes from a separate annotator component's own
# typesystem. Its shape here is empirically confirmed against the real
# CAS data rather than any typesystem document.
#
# Each entry is only injected if the combined typesystem doesn't
# already define that type name (see typesystem.py), so a real
# definition from your files always takes priority and duplicate-type
# errors are avoided.
INJECTED_FALLBACK_TYPES = {
    "org.texttechnologylab.annotation.type.MultimediaElement": """
<typeDescription>
    <name>org.texttechnologylab.annotation.type.MultimediaElement</name>
    <description>Injected fallback type (not found in provided typesystem files). Common base for most time-bounded annotations in this pipeline -- confirmed via real CAS data that timeStart/timeEnd are inherited from here, not redeclared on subtypes. width/height deliberately NOT included here: Detection (a MultimediaElement subtype) declares its own width/height for bbox size, and UIMA forbids a subtype redefining an inherited feature name.</description>
    <supertypeName>uima.tcas.Annotation</supertypeName>
    <features>
        <featureDescription><name>filename</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>duration</name><rangeTypeName>uima.cas.Double</rangeTypeName></featureDescription>
        <featureDescription><name>processed_at</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>fps</name><rangeTypeName>uima.cas.Double</rangeTypeName></featureDescription>
        <featureDescription><name>timeStart</name><rangeTypeName>uima.cas.Double</rangeTypeName></featureDescription>
        <featureDescription><name>timeEnd</name><rangeTypeName>uima.cas.Double</rangeTypeName></featureDescription>
    </features>
</typeDescription>
""",
    "org.texttechnologylab.annotation.type.AudioToken": """
<typeDescription>
    <name>org.texttechnologylab.annotation.type.AudioToken</name>
    <description>Injected fallback type (not found in provided typesystem files). Supertype of DiarizedAudioToken; confirmed via real CAS data that `value` is inherited from here.</description>
    <supertypeName>org.texttechnologylab.annotation.type.MultimediaElement</supertypeName>
    <features>
        <featureDescription><name>value</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
    </features>
</typeDescription>
""",
    "de.tudarmstadt.ukp.dkpro.core.api.metadata.type.DocumentMetaData": """
<typeDescription>
    <name>de.tudarmstadt.ukp.dkpro.core.api.metadata.type.DocumentMetaData</name>
    <description>Injected fallback type (not found in provided typesystem files)</description>
    <supertypeName>uima.tcas.Annotation</supertypeName>
    <features>
        <featureDescription><name>language</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>documentTitle</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>documentId</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>documentUri</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>isLastSegment</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
    </features>
</typeDescription>
""",
    "org.texttechnologylab.annotation.MetaData": """
<typeDescription>
    <name>org.texttechnologylab.annotation.MetaData</name>
    <description>Injected fallback type (not found in provided typesystem files). Bare base referenced by Emotion.model; model.MetaData/HuggingfaceMetaData below extend it so a feature declared with this range still accepts real model metadata instances.</description>
    <supertypeName>uima.tcas.Annotation</supertypeName>
    <features>
        <featureDescription><name>Source</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>ModelVersion</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>ModelName</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>Lang</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
    </features>
</typeDescription>
""",
    "org.texttechnologylab.annotation.model.MetaData": """
<typeDescription>
    <name>org.texttechnologylab.annotation.model.MetaData</name>
    <description>Injected fallback type (not found in provided typesystem files). Concrete metadata type used for real `model:MetaData` CAS elements.</description>
    <supertypeName>org.texttechnologylab.annotation.MetaData</supertypeName>
</typeDescription>
""",
    "org.texttechnologylab.annotation.model.HuggingfaceMetaData": """
<typeDescription>
    <name>org.texttechnologylab.annotation.model.HuggingfaceMetaData</name>
    <description>Injected fallback type (not found in provided typesystem files). MetaData variant emitted by HuggingFace-backed annotators.</description>
    <supertypeName>org.texttechnologylab.annotation.model.MetaData</supertypeName>
    <features>
        <featureDescription><name>HuggingfaceVersion</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>DependeciesVersion</name><rangeTypeName>uima.cas.StringArray</rangeTypeName></featureDescription>
    </features>
</typeDescription>
""",
    "org.texttechnologylab.uima.type.Embedding": """
<typeDescription>
    <name>org.texttechnologylab.uima.type.Embedding</name>
    <description>Injected fallback type (not found in provided typesystem files). Shape confirmed against a real Bundestag video-emotion CAS: a raw embedding vector string plus a reference back to whatever model produced it.</description>
    <supertypeName>uima.tcas.Annotation</supertypeName>
    <features>
        <featureDescription><name>embedding</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>ModelReference</name><rangeTypeName>org.texttechnologylab.annotation.MetaData</rangeTypeName></featureDescription>
    </features>
</typeDescription>
""",
    "org.texttechnologylab.annotation.AnnotationComment": """
<typeDescription>
    <name>org.texttechnologylab.annotation.AnnotationComment</name>
    <description>Injected fallback type (not found in provided typesystem files). Per-label key/value pair used by the GoEmotions-style raw classification.</description>
    <supertypeName>uima.cas.AnnotationBase</supertypeName>
    <features>
        <featureDescription><name>key</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>value</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>reference</name><rangeTypeName>uima.cas.TOP</rangeTypeName></featureDescription>
    </features>
</typeDescription>
""",
    "org.texttechnologylab.annotation.Emotion": """
<typeDescription>
    <name>org.texttechnologylab.annotation.Emotion</name>
    <description>Injected fallback type (not found in provided typesystem files). GoEmotions-style raw multi-label classification, distinct from annotation.emotion.Emotion -- shape confirmed against real CAS data.</description>
    <supertypeName>uima.tcas.Annotation</supertypeName>
    <features>
        <featureDescription><name>Emotions</name><rangeTypeName>uima.cas.FSArray</rangeTypeName><elementType>org.texttechnologylab.annotation.AnnotationComment</elementType></featureDescription>
        <featureDescription><name>model</name><rangeTypeName>org.texttechnologylab.annotation.MetaData</rangeTypeName></featureDescription>
    </features>
</typeDescription>
""",
}
