"""
Central configuration for the DUUI CAS parser.

Keeping every path / credential / type-name in one place means the
rest of the codebase never hardcodes a UIMA type name or a DB
setting inline -- everything is imported from here.
"""

import os

# --- File locations -------------------------------------------------

XMI_FILE = os.environ.get("DUUI_XMI_FILE", "cas/bundestag_full.xmi")

TYPESYSTEM_FILES = {
    "identity_emotion": os.environ.get(
        "DUUI_TS_IDENTITY_EMOTION", "IdentityEmotionTypeSystem.xml"
    ),
    "multimodal_identity": os.environ.get(
        "DUUI_TS_MULTIMODAL_IDENTITY", "MultimodalIdentityTypeSystem.xml"
    ),
    "emotion": os.environ.get("DUUI_TS_EMOTION", "EmotionTypeSystem.xml"),
}

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
    "model_meta_data": "org.texttechnologylab.annotation.model.MetaData",
    "shot": "org.texttechnologylab.annotation.video.Shot",
    "speaker_sentence": "org.texttechnologylab.annotation.audio.SpeakerSentence",
    "diarized_audio_token": "org.texttechnologylab.annotation.type.DiarizedAudioToken",
    "global_person": "org.texttechnologylab.annotation.identity.GlobalPerson",
    "person": "org.texttechnologylab.annotation.identity.Person",
    "face_identity": "org.texttechnologylab.annotation.identity.FaceIdentity",
    "voice_identity": "org.texttechnologylab.annotation.identity.VoiceIdentity",
    "person_track": "org.texttechnologylab.annotation.video.PersonTrack",
    "face_detection": "org.texttechnologylab.annotation.video.FaceDetection",
    "person_detection": "org.texttechnologylab.annotation.video.PersonDetection",
    "emotion": "org.texttechnologylab.annotation.emotion.Emotion",
}

# Java supertypes that are missing from the Python-side typesystem and
# need to be swapped for a standard UIMA annotation type before cassis
# can load the CAS.
SUPERTYPE_PATCHES = {
    "org.texttechnologylab.annotation.type.AudioToken": "uima.tcas.Annotation",
    "org.texttechnologylab.annotation.type.MultimediaElement": "uima.tcas.Annotation",
}

# Base type descriptions injected into the *first* typesystem only,
# to avoid "duplicate type" errors when merging.
INJECTED_BASE_TYPES_XML = """
<typeDescription>
    <name>org.texttechnologylab.annotation.type.MultimediaElement</name>
    <description>Injected Base Type for Python</description>
    <supertypeName>uima.tcas.Annotation</supertypeName>
    <features>
        <featureDescription><name>filename</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>duration</name><rangeTypeName>uima.cas.Double</rangeTypeName></featureDescription>
        <featureDescription><name>processed_at</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
        <featureDescription><name>fps</name><rangeTypeName>uima.cas.Double</rangeTypeName></featureDescription>
        <featureDescription><name>width</name><rangeTypeName>uima.cas.Integer</rangeTypeName></featureDescription>
        <featureDescription><name>height</name><rangeTypeName>uima.cas.Integer</rangeTypeName></featureDescription>
    </features>
</typeDescription>
<typeDescription>
    <name>de.tudarmstadt.ukp.dkpro.core.api.metadata.type.DocumentMetaData</name>
    <description>Injected Base Type for Python</description>
    <supertypeName>uima.tcas.Annotation</supertypeName>
    <features>
        <featureDescription><name>documentTitle</name><rangeTypeName>uima.cas.String</rangeTypeName></featureDescription>
    </features>
</typeDescription>
"""
