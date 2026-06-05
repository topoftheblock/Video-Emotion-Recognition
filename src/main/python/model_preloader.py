import torch
from transformers import pipeline

print("Pre-loading model...")
device = 0 if torch.cuda.is_available() else -1
classifier = pipeline(
    task="audio-classification", 
    model="firdhokk/speech-emotion-recognition-with-openai-whisper-large-v3",
    device=device
)
print("Model loaded successfully!")
