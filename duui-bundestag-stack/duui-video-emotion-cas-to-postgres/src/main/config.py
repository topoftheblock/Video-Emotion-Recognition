"""
Central configuration for the DUUI CAS parser.

Keeping every path / credential / type-name in one place means the
rest of the codebase never hardcodes a UIMA type name or a DB
setting inline -- everything is imported from here.

Deliberately separate from the viewer's own config (see
duui-video-emotion-visualization-webapp/src/backend/config.py): the two containers are independent
images with independent code, and share nothing but the database and
the video store. The settings they *both* read -- DB_CONFIG and
VIDEO_MEDIA_DIR -- are defined in each of them from the same
environment variables, which is what keeps the two ends of those two
contracts pointing at the same place (see docker-compose.yml, where
both services get the same values).
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv is optional -- if it's not installed, real environment
    # variables (export FOO=bar, or set by your process manager) still
    # work fine; only the convenience of a local .env file is lost.
    pass

# --- File locations -------------------------------------------------

# Where the pipeline drops its CAS .xmi files. `python -m main`/
# `run_many()` with no explicit path argument import everything in
# here, so this is the "just run the importer" default for a whole
# batch. Read-only as far as this importer is concerned.
INPUT_XMI_DIR = os.environ.get("DUUI_INPUT_XMI_DIR", "cas")

# Where the video files those CAS files reference live. A separate
# setting from INPUT_XMI_DIR because the two do not have to sit
# together: point both at the same folder for the side-by-side layout,
# or at different folders when the pipeline keeps them apart. Either
# way a CAS is matched to its video by the exact filename the CAS
# records (see media.py), never by position.
#
# Unset means "wherever the .xmi files are" rather than a fixed
# default, so pointing the importer at one folder of pipeline output
# needs one setting, not two. docker-compose.yml chains the host-side
# mount the same way.
INPUT_VIDEO_DIR = os.environ.get("DUUI_INPUT_VIDEO_DIR") or INPUT_XMI_DIR

# Optional single-file default, kept for compatibility with the older
# one-CAS-at-a-time workflow: if DUUI_XMI_FILE is set explicitly, a
# no-argument run imports just that file instead of all of
# INPUT_XMI_DIR.
XMI_FILE = os.environ.get("DUUI_XMI_FILE")

# Which CAS view/sofa holds the video, for the case where no video file
# exists in INPUT_VIDEO_DIR and it has to be recovered from the CAS
# itself (see media.py). DUUI pipelines put the video on the
# `_InitialView` sofa and derive the other views from it, so that is
# the default; set DUUI_VIDEO_VIEW when a pipeline routes it elsewhere
# (e.g. a dedicated `videoView`, the way audio lands on `audioView`).
# Any other `video/*` sofa is still used as a fallback, so this only
# has to be set when the named view is genuinely different.
VIDEO_VIEW = os.environ.get("DUUI_VIDEO_VIEW", "_InitialView")

# What to do with a .xmi whose video (by filename) is already in the
# database. `skip` leaves it alone and does not even load the CAS --
# which is what makes re-running the importer over a growing drop
# folder close to free.
# `replace` deletes the existing video and everything hanging off it
# (the schema cascades) and imports the file fresh, for when a CAS has
# been re-exported and its rows should match the new version.
# Overridable per run with `--on-existing` on the command line.
ON_EXISTING_CHOICES = ("skip", "replace")
ON_EXISTING = os.environ.get("DUUI_ON_EXISTING", "skip")

# Bundled, non-code assets (the UIMA typesystem descriptors, the demo
# CAS) live under the source root's `resources/`, not in the `main`
# package. Resolved from this file rather than the working directory so
# `python -m main` works from anywhere; DUUI_TS_* still override.
RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"
_TYPESYSTEM_DIR = RESOURCES_DIR / "typesystems"

TYPESYSTEM_FILES = {
    "identity_emotion": os.environ.get(
        "DUUI_TS_IDENTITY_EMOTION",
        str(_TYPESYSTEM_DIR / "IdentityEmotionTypeSystem.xml"),
    ),
    "multimodal_identity": os.environ.get(
        "DUUI_TS_MULTIMODAL_IDENTITY",
        str(_TYPESYSTEM_DIR / "MultimodalIdentityTypeSystem.xml"),
    ),
    "emotion": os.environ.get(
        "DUUI_TS_EMOTION", str(_TYPESYSTEM_DIR / "EmotionTypeSystem.xml")
    ),
}

# --- Video media -------------------------------------------------------
# Where *served* video files live -- the one place both the importer
# (copies into it, see src/main/media.py) and the webapp (reads from it,
# see the viewer's src/backend/config.py copy of this setting) agree a
# video for `videos.filename = X` lives at `<VIDEO_MEDIA_DIR>/X`. This
# is the output side, deliberately separate from the input dirs above so the
# webapp only ever sees videos that belong to a committed DB row, and
# never depends on how the raw pipeline drop directory is laid out.
#
# Defaults to "cas" -- the same as the input dirs -- so a native (non-Docker)
# setup collapses the two into one directory and the copy step is a
# harmless no-op. In Docker they're genuinely different: the importer
# reads /data/input/xmi and writes /data/videos, and the webapp mounts
# /data/videos read-only (see docker-compose.yml).
VIDEO_MEDIA_DIR = os.environ.get("DUUI_VIDEO_DIR", "cas")

# --- Database ---------------------------------------------------------

DB_CONFIG = {
    "dbname": os.environ.get("DUUI_DB_NAME", "your_db"),
    "user": os.environ.get("DUUI_DB_USER", "your_user"),
    "password": os.environ.get("DUUI_DB_PASSWORD", "your_password"),
    "host": os.environ.get("DUUI_DB_HOST", "localhost"),
}

# --- UIMA type names ----------------------------------------------------
# Centralising these means a type-system rename only touches this file.
# Only types some parser step actually `select`s by name are listed.
# Types this parser reads but never selects -- Embedding,
# AnnotationComment, HuggingfaceMetaData -- are reached by following a
# feature off an annotation that *was* selected, so they need a
# definition (see INJECTED_FALLBACK_TYPES below) but no entry here.

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
    "shot": "org.texttechnologylab.annotation.video.Shot",
    "speaker_sentence": "org.texttechnologylab.annotation.audio.SpeakerSentence",
    "speaker_segment": "org.texttechnologylab.annotation.audio.SpeakerSegment",
    "diarized_audio_token": "org.texttechnologylab.annotation.type.DiarizedAudioToken",
    # NOTE: there is deliberately no `global_person` entry.
    # `identity.GlobalPerson` is absent from every shipped typesystem
    # and empty in every real CAS seen so far, and cross-video identity
    # is now computed from embeddings by a separate job (see
    # duui-video-emotion-global-identity/), so selecting the type here
    # bought nothing but a warning on every import.
    "person": "org.texttechnologylab.annotation.identity.Person",
    "face_identity": "org.texttechnologylab.annotation.identity.FaceIdentity",
    "voice_identity": "org.texttechnologylab.annotation.identity.VoiceIdentity",
    "person_track": "org.texttechnologylab.annotation.video.PersonTrack",
    "face_detection": "org.texttechnologylab.annotation.video.FaceDetection",
    "person_detection": "org.texttechnologylab.annotation.video.PersonDetection",
    "emotion": "org.texttechnologylab.annotation.emotion.Emotion",
    # Text-based GoEmotions analysis is a *different* type from the
    # per-frame video/audio Emotion above -- it lives directly under
    # `.annotation`, not `.annotation.emotion`.
    "goemotions_emotion": "org.texttechnologylab.annotation.Emotion",
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

# Types a real CAS carries that this importer deliberately does not read.
#
# The DUUI pipeline runs an NLP stage over the transcript sofa and stamps
# provenance on everything it touches, so the .xmi references DKPro's
# text-layer types and TTLab's annotator-metadata types. None of them is
# in TYPES above and no parser step selects them: the transcript comes
# from `DiarizedAudioToken` (the audio layer), and POS/NER are taken from
# the DiarizedAudioToken features themselves where present.
#
# cassis warns once per unknown type while loading the XMI and skips the
# annotation -- correct behaviour, but for these twelve it is noise that
# buries anything real, so `loading_cas_quietly` filters exactly these
# messages. Declaring them here instead of stubbing them in
# INJECTED_FALLBACK_TYPES is deliberate: a featureless stub would make
# cassis materialise thousands of annotations nobody reads, and then
# complain about their unknown features instead.
#
# Nothing outside this set is silenced. A type that goes missing because
# a typesystem file was dropped or renamed still warns loudly.
IGNORED_ABSENT_TYPES = frozenset({
    # DKPro text layer -- tokens/POS/NER on the transcript sofa.
    "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence",
    "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Token",
    "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Lemma",
    "de.tudarmstadt.ukp.dkpro.core.api.lexmorph.type.pos.POS",
    "de.tudarmstadt.ukp.dkpro.core.api.lexmorph.type.morph.MorphologicalFeatures",
    "de.tudarmstadt.ukp.dkpro.core.api.syntax.type.dependency.Dependency",
    "de.tudarmstadt.ukp.dkpro.core.api.syntax.type.dependency.ROOT",
    "de.tudarmstadt.ukp.dkpro.core.api.ner.type.NamedEntity",
    # TTLab provenance -- who annotated what, with which tool version.
    "org.texttechnologylab.duui.ReproducibleAnnotation",
    "org.texttechnologylab.annotation.DocumentModification",
    "org.texttechnologylab.annotation.AnnotatorMetaData",
    "org.texttechnologylab.annotation.SpacyAnnotatorMetaData",
})
