from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import psycopg2
from psycopg2.extras import RealDictCursor
import uvicorn

# --- 1. Configuration ---
DB_CONFIG = {
    "dbname": "your_db",
    "user": "your_user",
    "password": "your_password",
    "host": "localhost"
}

# In a real app, this might be served via an S3 link or a static file route.
# For this script, replace with a valid URL or path to your video.
SAMPLE_VIDEO_ID = 1  # Replace with a valid video_id from your database
VIDEO_URL = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4" 

app = FastAPI(title="Video Analytics Player")

# --- 2. Database Helper ---
def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

# --- 3. API Endpoint: Fetch Video Data ---
@app.get("/api/video/{video_id}/data")
def get_video_data(video_id: int):
    """Fetches detections and emotions for a specific video."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    cursor = conn.cursor()
    try:
        # Fetch Detections (FaceDetection)
        cursor.execute("""
            SELECT person_id, frame_index, t_time, x, y, w, h, detection_score 
            FROM FaceDetection 
            WHERE video_id = %s
            ORDER BY t_time ASC
        """, (video_id,))
        detections = cursor.fetchall()

        # Fetch Emotions (BaseEmotion)
        cursor.execute("""
            SELECT person_id, start_time, end_time, valence, arousal, dominant_label 
            FROM BaseEmotion 
            WHERE video_id = %s
        """, (video_id,))
        emotions = cursor.fetchall()

        return {
            "detections": detections,
            "emotions": emotions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# --- 4. Frontend Web Page ---
@app.get("/", response_class=HTMLResponse)
def serve_player():
    """Serves the HTML/JS frontend to the browser."""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DUUI Video Analytics Player</title>
        <style>
            body {{ font-family: sans-serif; background: #121212; color: white; padding: 20px; }}
            .player-container {{ position: relative; display: inline-block; }}
            video {{ display: block; max-width: 800px; border: 2px solid #333; }}
            /* The canvas is positioned directly over the video */
            canvas {{ position: absolute; top: 0; left: 0; pointer-events: none; }}
            .controls {{ margin-top: 15px; }}
        </style>
    </head>
    <body>
        <h2>DUUI Video Analytics Player</h2>
        
        <div class="player-container">
            <video id="videoPlayer" src="{VIDEO_URL}" width="800" controls crossorigin="anonymous"></video>
            <canvas id="overlayCanvas" width="800"></canvas>
        </div>

        <div class="controls">
            <p id="status">Loading data...</p>
        </div>

        <script>
            const videoId = {SAMPLE_VIDEO_ID};
            const video = document.getElementById('videoPlayer');
            const canvas = document.getElementById('overlayCanvas');
            const ctx = canvas.getContext('2d');
            const statusText = document.getElementById('status');
            
            let analyticsData = {{ detections: [], emotions: [] }};

            // 1. Match Canvas size to Video size once metadata is loaded
            video.addEventListener('loadedmetadata', () => {{
                canvas.width = video.clientWidth;
                canvas.height = video.clientHeight;
            }});

            // 2. Fetch Data from Python API
            async function loadData() {{
                try {{
                    const response = await fetch(`/api/video/${{videoId}}/data`);
                    analyticsData = await response.json();
                    statusText.innerText = `Data loaded! Detections: ${{analyticsData.detections.length}}, Emotions: ${{analyticsData.emotions.length}}`;
                }} catch (error) {{
                    statusText.innerText = 'Error loading data from database.';
                    console.error(error);
                }}
            }}

            // 3. Draw Loop synced with video playback
            video.addEventListener('timeupdate', () => {{
                const currentTime = video.currentTime;
                
                // Clear previous frame
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                // Find active detections for this exact timestamp (allow a small time window e.g. 0.1s)
                const activeDetections = analyticsData.detections.filter(d => 
                    Math.abs(d.t_time - currentTime) < 0.1
                );

                // Find active emotions happening right now
                const activeEmotions = analyticsData.emotions.filter(e => 
                    currentTime >= e.start_time && currentTime <= e.end_time
                );

                // Draw each detection
                activeDetections.forEach(det => {{
                    // Convert normalized coordinates (0 to 1) to actual canvas pixels
                    const x = det.x * canvas.width;
                    const y = det.y * canvas.height;
                    const w = det.w * canvas.width;
                    const h = det.h * canvas.height;

                    // Draw Bounding Box
                    ctx.strokeStyle = '#00ffcc';
                    ctx.lineWidth = 3;
                    ctx.strokeRect(x, y, w, h);

                    // Draw Emotion Text if available for this person
                    const personEmotion = activeEmotions.find(e => e.person_id === det.person_id);
                    if (personEmotion) {{
                        ctx.fillStyle = '#00ffcc';
                        ctx.font = 'bold 16px Arial';
                        // Draw background for text readability
                        const text = `${{personEmotion.dominant_label}} (V:${{personEmotion.valence.toFixed(2)}})`;
                        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
                        ctx.fillRect(x, y - 25, ctx.measureText(text).width + 10, 25);
                        
                        // Draw text
                        ctx.fillStyle = '#ffffff';
                        ctx.fillText(text, x + 5, y - 7);
                    }}
                }});
            }});

            // Initialize
            loadData();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- 5. Runner ---
if __name__ == "__main__":
    print("Starting server... Open http://localhost:8000 in your browser.")
    uvicorn.run(app, host="0.0.0.0", port=8000)