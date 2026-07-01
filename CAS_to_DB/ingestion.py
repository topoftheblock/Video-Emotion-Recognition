import psycopg2
from cassis import load_typesystem, load_cas_from_json

def export_cas_to_db(cas_json_path, db_connection, video_id):
    # 1. Load the TypeSystem and the CAS
    with open('TypeSystem.xml', 'rb') as f:
        typesystem = load_typesystem(f)
    with open(cas_json_path, 'rb') as f:
        cas = load_cas_from_json(f, typesystem=typesystem)

    cursor = db_connection.cursor()

    try:
        # --- MAPPING IDENTITIES ---
        # Select all Person annotations across the entire document
        persons = cas.select("org.texttechnologylab.annotation.identity.Person")
        for p in persons:
            # Insert into Person table
            cursor.execute(
                "INSERT INTO Person (person_id, video_id, clip_label) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (p.personId, video_id, p.label)
            )

        # --- MAPPING PRESENCE & DETECTIONS ---
        video_view = cas.get_view("VideoView")
        face_detections = video_view.select("org.texttechnologylab.annotation.video.FaceDetection")
        
        for fd in face_detections:
            # Note: In a real script, you'd resolve the 'track' or 'presence' reference here
            # For simplicity, we directly insert the detection box
            cursor.execute(
                """INSERT INTO FaceDetection (person_id, video_id, frame_index, t_time, x, y, w, h) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (fd.track.face.person.personId, video_id, fd.frameIndex, fd.begin / 1000.0, fd.x, fd.y, fd.width, fd.height)
            )

        # --- MAPPING EMOTIONS (Base + Scores) ---
        emotions = cas.select("org.texttechnologylab.annotation.emotion.Emotion")
        
        for emo in emotions:
            # 1. Insert the BaseEmotion
            cursor.execute(
                """INSERT INTO BaseEmotion (video_id, modality, granularity, start_time, end_time, valence, arousal) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING emotion_id""",
                (video_id, emo.modality, emo.granularity, emo.begin / 1000.0, emo.end / 1000.0, emo.valence, emo.arousal)
            )
            # Retrieve the auto-generated Primary Key
            base_emotion_id = cursor.fetchone()[0]

            # 2. Loop through the FSArray of EmotionScores and insert them
            if emo.scores:
                for score_obj in emo.scores:
                    cursor.execute(
                        "INSERT INTO EmotionScore (emotion_id, label, score) VALUES (%s, %s, %s)",
                        (base_emotion_id, score_obj.label, score_obj.score)
                    )

        # Commit all transactions for this CAS
        db_connection.commit()

    except Exception as e:
        db_connection.rollback()
        print(f"Failed to map CAS to DB: {e}")
    finally:
        cursor.close()