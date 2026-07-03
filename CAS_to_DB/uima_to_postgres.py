from cassis import load_cas_from_xmi
import psycopg2
from psycopg2 import sql
import uuid
import os

# --- 1. Configuration ---
XMI_FILE = "cas/bundestag_full.xmi"  # Replace with your XMI file path
DB_CONFIG = {
    "dbname": "your_db",
    "user": "your_user",
    "password": "your_password",
    "host": "localhost"
}

# --- 2. Connect to PostgreSQL ---
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- 3. Helper: Get or Insert ID ---
def get_or_insert_id(cursor, conn, table, column, value):
    """Get existing ID or insert and return new ID."""
    if value is None:
        return None
    cursor.execute(
        sql.SQL("SELECT {} FROM {} WHERE {} = %s").format(
            sql.Identifier(column),
            sql.Identifier(table),
            sql.Identifier(column)
        ),
        (value,)
    )
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute(
            sql.SQL("INSERT INTO {} ({}) VALUES (%s) RETURNING {}").format(
                sql.Identifier(table),
                sql.Identifier(column),
                sql.Identifier(column)
            ),
            (value,)
        )
        return value

def get_xmi_id(feature_struct):
    """Safely extract the XMI ID from a cassis FeatureStructure."""
    if feature_struct is None:
        return None
    if hasattr(feature_struct, "xmiID"):
        return feature_struct.xmiID
    return None

# --- 4. Parse and Insert All Annotations ---
def parse_and_insert(cas, cursor, conn):
    global_video_id = None
    
    # --- 4.1 Video (from MultimediaElement or DocumentMetaData) ---
    for multimedia in cas.select("org.texttechnologylab.annotation.type.MultimediaElement"):
        global_video_id = get_xmi_id(multimedia)
        get_or_insert_id(cursor, conn, "Video", "video_id", global_video_id)
        cursor.execute(
            """
            INSERT INTO Video (video_id, filename, duration, processed_at, fps, width, height)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE SET
                filename = EXCLUDED.filename, duration = EXCLUDED.duration, 
                processed_at = EXCLUDED.processed_at, fps = EXCLUDED.fps, 
                width = EXCLUDED.width, height = EXCLUDED.height
            """,
            (
                global_video_id,
                getattr(multimedia, "filename", None),
                getattr(multimedia, "duration", None),
                getattr(multimedia, "processed_at", None),
                getattr(multimedia, "fps", None),
                getattr(multimedia, "width", None),
                getattr(multimedia, "height", None),
            )
        )
        break
    
    if not global_video_id:
        # Fallback if no MultimediaElement is present but DocumentMetaData is
        for md in cas.select("de.tudarmstadt.ukp.dkpro.core.api.metadata.type.DocumentMetaData"):
            global_video_id = get_xmi_id(md)
            get_or_insert_id(cursor, conn, "Video", "video_id", global_video_id)
            cursor.execute(
                "INSERT INTO Video (video_id, filename) VALUES (%s, %s) ON CONFLICT (video_id) DO NOTHING",
                (global_video_id, getattr(md, "documentTitle", None))
            )
            break

    # --- 4.2 Model ---
    for metadata in cas.select("org.texttechnologylab.annotation.MetaData"):
        model_id = get_xmi_id(metadata)
        get_or_insert_id(cursor, conn, "Model", "model_id", model_id)
        cursor.execute(
            """
            INSERT INTO Model (model_id, name, version, source)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (model_id) DO NOTHING
            """,
            (
                model_id,
                getattr(metadata, "ModelName", getattr(metadata, "name", None)),
                getattr(metadata, "ModelVersion", getattr(metadata, "version", None)),
                getattr(metadata, "Source", getattr(metadata, "source", None)),
            )
        )

    # --- 4.3 Segment (Shot & Sentence) ---
    for shot in cas.select("org.texttechnologylab.annotation.video.Shot"):
        segment_id = get_xmi_id(shot)
        get_or_insert_id(cursor, conn, "Segment", "segment_id", segment_id)
        cursor.execute(
            """
            INSERT INTO Segment (segment_id, video_id, kind, seg_index, start_time, end_time, begin, end)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (segment_id) DO NOTHING
            """,
            (
                segment_id,
                global_video_id,
                "shot",
                getattr(shot, "shotIndex", None),
                getattr(shot, "timeStart", None),
                getattr(shot, "timeEnd", None),
                shot.begin,
                shot.end,
            )
        )

    for sentence in cas.select("org.texttechnologylab.annotation.audio.SpeakerSentence"):
        segment_id = get_xmi_id(sentence)
        get_or_insert_id(cursor, conn, "Segment", "segment_id", segment_id)
        
        person_id = None
        if hasattr(sentence, "speakerSegment") and sentence.speakerSegment:
            if hasattr(sentence.speakerSegment, "voice") and sentence.speakerSegment.voice:
                person_id = get_xmi_id(getattr(sentence.speakerSegment.voice, "person", None))

        cursor.execute(
            """
            INSERT INTO Segment (segment_id, video_id, kind, start_time, end_time, begin, end, person_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (segment_id) DO NOTHING
            """,
            (
                segment_id,
                global_video_id,
                "sentence",
                getattr(sentence, "timeStart", None),
                getattr(sentence, "timeEnd", None),
                sentence.begin,
                sentence.end,
                person_id
            )
        )

    # --- 4.3.1 LinguisticToken ---
    for token in cas.select("org.texttechnologylab.annotation.type.DiarizedAudioToken"):
        token_id = get_xmi_id(token)
        get_or_insert_id(cursor, conn, "LinguisticToken", "token_id", token_id)
        cursor.execute(
            """
            INSERT INTO LinguisticToken (token_id, video_id, segment_id, start_time, end_time, begin, end, word, pos_tag, ner_label)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (token_id) DO NOTHING
            """,
            (
                token_id,
                global_video_id,
                get_xmi_id(getattr(token, "segment", None)),
                getattr(token, "timeStart", None),
                getattr(token, "timeEnd", None),
                token.begin,
                token.end,
                getattr(token, "word", token.get_covered_text()),
                getattr(token, "pos_tag", None),
                getattr(token, "ner_label", None)
            )
        )

    # --- GlobalPerson ---
    for g_person in cas.select("org.texttechnologylab.annotation.identity.GlobalPerson"):
        gp_id = get_xmi_id(g_person)
        get_or_insert_id(cursor, conn, "GlobalPerson", "global_person_id", gp_id)
        cursor.execute(
            "INSERT INTO GlobalPerson (global_person_id, real_name) VALUES (%s, %s) ON CONFLICT (global_person_id) DO NOTHING",
            (gp_id, getattr(g_person, "real_name", getattr(g_person, "name", None)))
        )

    # --- 4.4 Person ---
    for person in cas.select("org.texttechnologylab.annotation.identity.Person"):
        person_id = get_xmi_id(person)
        get_or_insert_id(cursor, conn, "Person", "person_id", person_id)
        
        global_person_id = get_xmi_id(getattr(person, "globalPerson", None))
        
        cursor.execute(
            """
            INSERT INTO Person (person_id, video_id, global_person_id, clip_label, match_score)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
            """,
            (
                person_id,
                global_video_id,
                global_person_id,
                getattr(person, "clip_label", getattr(person, "label", None)),
                getattr(person, "match_score", None),
            )
        )

    # --- 4.5 FaceEmbedding ---
    for face in cas.select("org.texttechnologylab.annotation.identity.FaceIdentity"):
        embedding_id = get_xmi_id(face)
        get_or_insert_id(cursor, conn, "FaceEmbedding", "embedding_id", embedding_id)
        person_id = get_xmi_id(getattr(face, "person", None))
        model_id = get_xmi_id(getattr(face, "model", None))
        cursor.execute(
            """
            INSERT INTO FaceEmbedding (embedding_id, person_id, model_id, embedding)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (embedding_id) DO NOTHING
            """,
            (
                embedding_id,
                person_id,
                model_id,
                str(face.embeddings) if hasattr(face, "embeddings") else None,
            )
        )

    # --- 4.6 VoiceEmbedding ---
    for voice in cas.select("org.texttechnologylab.annotation.identity.VoiceIdentity"):
        embedding_id = get_xmi_id(voice)
        get_or_insert_id(cursor, conn, "VoiceEmbedding", "embedding_id", embedding_id)
        person_id = get_xmi_id(getattr(voice, "person", None))
        model_id = get_xmi_id(getattr(voice, "model", None))
        cursor.execute(
            """
            INSERT INTO VoiceEmbedding (embedding_id, person_id, model_id, embedding)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (embedding_id) DO NOTHING
            """,
            (
                embedding_id,
                person_id,
                model_id,
                str(voice.embeddings) if hasattr(voice, "embeddings") else None,
            )
        )

    # --- 4.7 Presence (from PersonTrack) ---
    for track in cas.select("org.texttechnologylab.annotation.video.PersonTrack"):
        presence_id = get_xmi_id(track)
        get_or_insert_id(cursor, conn, "Presence", "presence_id", presence_id)
        person_id = None
        if hasattr(track, "face") and track.face:
            person_id = get_xmi_id(getattr(track.face, "person", None))
        elif hasattr(track, "person") and track.person:
            person_id = get_xmi_id(track.person)

        cursor.execute(
            """
            INSERT INTO Presence (presence_id, person_id, video_id, modality, start_time, end_time, begin, end)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (presence_id) DO NOTHING
            """,
            (
                presence_id,
                person_id,
                global_video_id,
                getattr(track, "modality", None),
                getattr(track, "timeStart", getattr(track, "start_time", None)),
                getattr(track, "timeEnd", getattr(track, "end_time", None)),
                track.begin,
                track.end,
            )
        )

    # --- 4.8 FaceDetection ---
    for detection in cas.select("org.texttechnologylab.annotation.video.FaceDetection"):
        detection_id = get_xmi_id(detection)
        get_or_insert_id(cursor, conn, "FaceDetection", "detection_id", detection_id)
        presence_id = get_xmi_id(getattr(detection, "track", None))
        person_id = None
        if getattr(detection, "track", None) and getattr(detection.track, "face", None):
             person_id = get_xmi_id(getattr(detection.track.face, "person", None))

        cursor.execute(
            """
            INSERT INTO FaceDetection (detection_id, presence_id, person_id, video_id, frame_index, t_time, x, y, w, h, detection_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (detection_id) DO NOTHING
            """,
            (
                detection_id, presence_id, person_id, global_video_id,
                getattr(detection, "frameIndex", None), getattr(detection, "timeStart", None),
                getattr(detection, "x", None), getattr(detection, "y", None),
                getattr(detection, "width", None), getattr(detection, "height", None),
                getattr(detection, "detectionScore", None),
            )
        )

    # --- 4.8.1 PersonDetection ---
    for detection in cas.select("org.texttechnologylab.annotation.video.PersonDetection"):
        detection_id = get_xmi_id(detection)
        get_or_insert_id(cursor, conn, "PersonDetection", "detection_id", detection_id)
        presence_id = get_xmi_id(getattr(detection, "track", None))
        person_id = None
        if getattr(detection, "track", None) and getattr(detection.track, "face", None):
             person_id = get_xmi_id(getattr(detection.track.face, "person", None))

        cursor.execute(
            """
            INSERT INTO PersonDetection (detection_id, presence_id, person_id, video_id, frame_index, t_time, x, y, w, h, detection_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (detection_id) DO NOTHING
            """,
            (
                detection_id, presence_id, person_id, global_video_id,
                getattr(detection, "frameIndex", None), getattr(detection, "timeStart", None),
                getattr(detection, "x", None), getattr(detection, "y", None),
                getattr(detection, "width", None), getattr(detection, "height", None),
                getattr(detection, "detectionScore", None),
            )
        )

    # --- 4.9 BaseEmotion & EmotionScore ---
    for emotion in cas.select("org.texttechnologylab.annotation.emotion.Emotion"):
        emotion_id = get_xmi_id(emotion)
        get_or_insert_id(cursor, conn, "BaseEmotion", "emotion_id", emotion_id)
        
        person_id = getattr(emotion, "personId", None)
        
        cursor.execute(
            """
            INSERT INTO BaseEmotion (emotion_id, person_id, video_id, modality, granularity, start_time, end_time, begin, end, frame_index, x, y, w, h, valence, arousal, dominance, dominant_label)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (emotion_id) DO NOTHING
            """,
            (
                emotion_id,
                person_id,
                global_video_id,
                getattr(emotion, "modality", None),
                getattr(emotion, "granularity", None),
                getattr(emotion, "timeStart", None),
                getattr(emotion, "timeEnd", None),
                emotion.begin,
                emotion.end,
                getattr(emotion, "frameIndex", None),
                getattr(emotion, "x", None),
                getattr(emotion, "y", None),
                getattr(emotion, "width", None),
                getattr(emotion, "height", None),
                getattr(emotion, "valence", None),
                getattr(emotion, "arousal", None),
                getattr(emotion, "dominance", None),
                getattr(emotion, "dominant_label", None),
            )
        )

        # 4.10 EmotionScore (Nested scores attribute in Emotion)
        if hasattr(emotion, "scores") and emotion.scores:
            for score in emotion.scores:
                cursor.execute(
                    """
                    INSERT INTO EmotionScore (emotion_id, label, score)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (emotion_id, label) DO NOTHING
                    """,
                    (
                        emotion_id,
                        getattr(score, "label", None),
                        getattr(score, "score", None),
                    )
                )

        # 4.11 FusedEmotion 
        if hasattr(emotion, "aggregatedFrom") and emotion.aggregatedFrom:
            fused_id = get_or_insert_id(cursor, conn, "FusedEmotion", "fused_id", emotion_id)
            cursor.execute(
                """
                INSERT INTO FusedEmotion (fused_id, video_id, person_id, fusion_method, target_modality, start_time, end_time, valence, arousal, dominant_label)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fused_id) DO NOTHING
                """,
                (
                    fused_id,
                    global_video_id,
                    person_id,
                    getattr(emotion, "fusion_method", None),
                    getattr(emotion, "target_modality", None),
                    getattr(emotion, "timeStart", None),
                    getattr(emotion, "timeEnd", None),
                    getattr(emotion, "valence", None),
                    getattr(emotion, "arousal", None),
                    getattr(emotion, "dominant_label", None),
                )
            )

            # 4.12 EmotionFusionReference
            for source_emotion in emotion.aggregatedFrom:
                source_emotion_id = get_xmi_id(source_emotion)
                get_or_insert_id(cursor, conn, "BaseEmotion", "emotion_id", source_emotion_id)
                cursor.execute(
                    """
                    INSERT INTO EmotionFusionReference (fused_id, source_emotion_id)
                    VALUES (%s, %s)
                    ON CONFLICT (fused_id, source_emotion_id) DO NOTHING
                    """,
                    (fused_id, source_emotion_id)
                )

# --- 5. Main ---
if __name__ == "__main__":
    cas = load_cas_from_xmi(XMI_FILE)
    conn = get_db_connection()
    cursor = conn.cursor()
    parse_and_insert(cas, cursor, conn)
    conn.commit()
    cursor.close()
    conn.close()
    print("Parser completed successfully!")