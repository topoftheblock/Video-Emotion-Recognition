from moviepy import VideoFileClip

def extract_audio(video_path, output_audio_path):
    # Load the video file
    video = VideoFileClip(video_path)
    
    # Extract the audio stream
    audio = video.audio
    
    # Write the audio file to disk
    # ffmpeg_params ensures it matches the 16kHz Mono WAV format required by AI models
    audio.write_audiofile(
        output_audio_path,
        fps=16000,          # 16kHz sample rate
        nbytes=2,           # 16-bit depth
        codec='pcm_s16le',  # WAV PCM codec
        ffmpeg_params=["-ac", "1"] # Force mono channel
    )
    
    # Close clips to release system resources
    audio.close()
    video.close()
    print(f"Audio successfully extracted and saved to {output_audio_path}")

# Example usage
extract_audio("/Users/andreasblock/Desktop/Video-Emotion-Recognition/Speeches/ID2021013800__7629058_h264_640_360_1000kb_baseline_de_1000.mp4", "/Users/andreasblock/Desktop/Video-Emotion-Recognition/Audio/extracted_speech.wav")