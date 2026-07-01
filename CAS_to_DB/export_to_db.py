import psycopg2
from cassis import load_typesystem, load_cas_from_json

# --- Database Configuration ---
DB_CONFIG = {
    "dbname": "duui_database",
    "user": "postgres",
    "password": "your_password",
    "host": "localhost",
    "port": "5432"
}

def export_cas_to_db(cas_json_path, ts_xml_path, video_id):
    print("Loading TypeSystem and CAS...")
    with open(ts_xml_path, 'rb') as f:
        typesystem = load_typesystem(f)
    with open(cas_json_path, 'rb') as f:
        cas = load_cas_from_json(f, typesystem=typesystem)

    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        print("Extracting Persons...")
        persons = cas.select("org.texttechnologylab.annotation.identity.Person")
        for p in persons:
            cursor.execute(
                "INSERT INTO persons (person_id, video_id, clip_label) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (p.personId, video_id, p.label)
            )

        print("Extracting Face Detections...")
        try:
            video_view = cas.get_view("VideoView")
            face_detections = video_view.select("org.texttechnologylab.annotation.video.FaceDetection")
            for fd in face_detections:
                person_id = fd.track.face.person.personId if fd.track and fd.track.face and fd.track.face.person else None
                if person_id:
                    cursor.execute(
                        """INSERT INTO face_detections (person_id, video_id, frame_index, t_time, x, y, w, h) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (person_id, video_id, fd.frameIndex, fd.begin / 1000.0, fd.x, fd.y, fd.width, fd.height)
                    )
        except Exception as e:
            print(f"Skipping Face Detections (View might not exist): {e}")

        print("Extracting Emotions...")
        emotions = cas.select("org.texttechnologylab.annotation.emotion.Emotion")
        for emo in emotions:
            cursor.execute(
                """INSERT INTO base_emotions (video_id, modality, granularity, start_time, end_time, valence, arousal) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING emotion_id""",
                (video_id, emo.modality, emo.granularity, emo.begin / 1000.0, emo.end / 1000.0, emo.valence, emo.arousal)
            )
            base_emotion_id = cursor.fetchone()[0]

            if emo.scores:
                for score_obj in emo.scores:
                    cursor.execute(
                        "INSERT INTO emotion_scores (emotion_id, label, score) VALUES (%s, %s, %s)",
                        (base_emotion_id, score_obj.label, score_obj.score)
                    )

        conn.commit()
        print("Successfully exported CAS to Database!")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: Transaction rolled back. Details: {e}")
    finally:
        cursor.close()
        conn.close()

# Example Usage
if __name__ == "__main__":
    # Ensure these files exist in your directory
    export_cas_to_db("final_cas.json", "TypeSystem.xml", video_id=1)    