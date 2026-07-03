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
        new_id = str(uuid.uuid4())
        cursor.execute(
            sql.SQL("INSERT INTO {} ({}) VALUES (%s) RETURNING {}").format(
                sql.Identifier(table),
                sql.Identifier(column),
                sql.Identifier(column)
            ),
            (value,)
        )
        conn.commit()
        return cursor.fetchone()[0]

# --- 4. Parse and Insert All Annotations ---
def parse_and_insert(cas, cursor, conn):
    # --- 4.1 Video (from MultimediaElement) ---
    for multimedia in cas.select("org.texttechnologylab.annotation.type.MultimediaElement"):
        video_id = get_or_insert_id(cursor, conn, "Video", "video_id", multimedia.xmi.id)
        cursor.execute(
            """
            INSERT INTO Video (video_id, filename, duration, processed_at, fps, width, height)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO NOTHING
            """,
            (
                video_id,
                getattr(multimedia, "filename", None),
                getattr(multimedia, "duration", None),
                getattr(multimedia, "processed_at", None),
                getattr(multimedia, "fps", None),
                getattr(multimedia, "width", None),
                getattr(multimedia, "height", None),
            )
        )

    # --- 4.2 Model ---
    for metadata in cas.select("org.texttechnologylab.annotation.MetaData"):
        model_id = get_or_insert_id(cursor, conn, "Model", "model_id", metadata.xmi.id)
        cursor.execute(
            """
            INSERT INTO Model (model_id, name, version, source)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (model_id) DO NOTHING
            """,
            (
                model_id,
                getattr(metadata, "name", None),
                getattr(metadata, "version", None),
                getattr(metadata, "source", None),
            )
        )

    # --- 4.3 Segment (from Shot) ---
    for shot in cas.select("org.texttechnologylab.annotation.video.Shot"):
        segment_id = get_or_insert_id(cursor, conn, "Segment", "segment_id", shot.xmi.id)
        video_id = get_or_insert_id(cursor, conn, "Video", "video_id", shot.reference.xmi.id)
        cursor.execute(
            """
            INSERT INTO Segment (segment_id, video_id, kind, seg_index, start_time, end_time, begin, end)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (segment_id) DO NOTHING
            """,
            (
                segment_id,
                video_id,
                "shot",
                shot.shotIndex,
                shot.begin,
                shot.end,
                shot.begin,
                shot.end,
            )
        )

    # --- 4.4 Person ---
    for person in cas.select("org.texttechnologylab.annotation.identity.Person"):
        person_id = get_or_insert_id(cursor, conn, "Person", "person_id", person.xmi.id)
        cursor.execute(
            """
            INSERT INTO Person (person_id, global_person_id, real_name, clip_label, match_score)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (person_id) DO NOTHING
            """,
            (
                person_id,
                getattr(person, "personId", None),
                getattr(person, "label", None),
                getattr(person, "clip_label", None),
                getattr(person, "match_score", None),
            )
        )

    # --- 4.5 FaceEmbedding ---
    for face in cas.select("org.texttechnologylab.annotation.identity.FaceIdentity"):
        embedding_id = get_or_insert_id(cursor, conn, "FaceEmbedding", "embedding_id", face.xmi.id)
        person_id = get_or_insert_id(cursor, conn, "Person", "person_id", face.person.xmi.id)
        model_id = get_or_insert_id(cursor, conn, "Model", "model_id", face.model.xmi.id)
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
        embedding_id = get_or_insert_id(cursor, conn, "VoiceEmbedding", "embedding_id", voice.xmi.id)
        person_id = get_or_insert_id(cursor, conn, "Person", "person_id", voice.person.xmi.id)
        model_id = get_or_insert_id(cursor, conn, "Model", "model_id", voice.model.xmi.id)
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
        presence_id = get_or_insert_id(cursor, conn, "Presence", "presence_id", track.xmi.id)
        person_id = get_or_insert_id(cursor, conn, "Person", "person_id", track.face.person.xmi.id)
        video_id = get_or_insert_id(cursor, conn, "Video", "video_id", track.shot.reference.xmi.id)
        cursor.execute(
            """
            INSERT INTO Presence (presence_id, person_id, video_id, modality, start_time, end_time, begin, end)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (presence_id) DO NOTHING
            """,
            (
                presence_id,
                person_id,
                video_id,
                getattr(track, "modality", None),
                track.begin,
                track.end,
                track.begin,
                track.end,
            )
        )

    # --- 4.8 Detection ---
    for detection in cas.select("org.texttechnologylab.annotation.video.Detection"):
        detection_id = get_or_insert_id(cursor, conn, "Detection", "detection_id", detection.xmi.id)
        presence_id = get_or_insert_id(cursor, conn, "Presence", "presence_id", detection.track.xmi.id)
        person_id = get_or_insert_id(cursor, conn, "Person", "person_id", detection.track.face.person.xmi.id)
        video_id = get_or_insert_id(cursor, conn, "Video", "video_id", detection.track.shot.reference.xmi.id)
        cursor.execute(
            """
            INSERT INTO Detection (detection_id, presence_id, person_id, video_id, frame_index, t_time, x, y, w, h, detection_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (detection_id) DO NOTHING
            """,
            (
                detection_id,
                presence_id,
                person_id,
                video_id,
                getattr(detection, "frameIndex", None),
                getattr(detection, "t_time", None),
                detection.x,
                detection.y,
                detection.width,
                detection.height,
                getattr(detection, "detectionScore", None),
            )
        )

    # --- 4.9 BaseEmotion ---
    for emotion in cas.select("org.texttechnologylab.annotation.emotion.Emotion"):
        emotion_id = get_or_insert_id(cursor, conn, "BaseEmotion", "emotion_id", emotion.xmi.id)
        person_id = get_or_insert_id(cursor, conn, "Person", "person_id", emotion.personId)
        video_id = get_or_insert_id(cursor, conn, "Video", "video_id", emotion.reference.xmi.id)
        cursor.execute(
            """
            INSERT INTO BaseEmotion (emotion_id, person_id, video_id, modality, granularity, start_time, end_time, begin, end, frame_index, x, y, w, h, valence, arousal, dominance, dominant_label)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (emotion_id) DO NOTHING
            """,
            (
                emotion_id,
                person_id,
                video_id,
                getattr(emotion, "modality", None),
                getattr(emotion, "granularity", None),
                emotion.begin,
                emotion.end,
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

    # --- 4.10 EmotionScore ---
    for score in cas.select("org.texttechnologylab.annotation.emotion.EmotionScore"):
        emotion_id = get_or_insert_id(cursor, conn, "BaseEmotion", "emotion_id", score.reference.xmi.id)
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

    # --- 4.11 FusedEmotion ---
    for fused in cas.select("org.texttechnologylab.annotation.emotion.Emotion"):
        if hasattr(fused, "aggregatedFrom"):
            fused_id = get_or_insert_id(cursor, conn, "FusedEmotion", "fused_id", fused.xmi.id)
            video_id = get_or_insert_id(cursor, conn, "Video", "video_id", fused.reference.xmi.id)
            person_id = get_or_insert_id(cursor, conn, "Person", "person_id", fused.personId)
            cursor.execute(
                """
                INSERT INTO FusedEmotion (fused_id, video_id, person_id, fusion_method, target_modality, start_time, end_time, valence, arousal, dominant_label)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fused_id) DO NOTHING
                """,
                (
                    fused_id,
                    video_id,
                    person_id,
                    getattr(fused, "fusion_method", None),
                    getattr(fused, "target_modality", None),
                    fused.begin,
                    fused.end,
                    getattr(fused, "valence", None),
                    getattr(fused, "arousal", None),
                    getattr(fused, "dominant_label", None),
                )
            )

    # --- 4.12 EmotionFusionReference ---
    for ref in cas.select("org.texttechnologylab.annotation.emotion.Emotion"):
        if hasattr(ref, "aggregatedFrom"):
            fused_id = get_or_insert_id(cursor, conn, "FusedEmotion", "fused_id", ref.xmi.id)
            for source_emotion in ref.aggregatedFrom:
                source_emotion_id = get_or_insert_id(cursor, conn, "BaseEmotion", "emotion_id", source_emotion.xmi.id)
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
    # Load CAS
    cas = load_cas_from_xmi(XMI_FILE)

    # Connect to DB
    conn = get_db_connection()
    cursor = conn.cursor()

    # Parse and insert
    parse_and_insert(cas, cursor, conn)

    # Commit and close
    conn.commit()
    cursor.close()
    conn.close()
    print("Parser completed successfully!")