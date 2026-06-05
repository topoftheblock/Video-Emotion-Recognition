from transformers import pipeline

# Initialize the Hugging Face audio classification pipeline
# We are using a popular Whisper Large V3 model fine-tuned for SER
classifier = pipeline(
    task="audio-classification", 
    model="firdhokk/speech-emotion-recognition-with-openai-whisper-large-v3",
    device=0 # Set to -1 if using CPU
)

# Run the classifier on your audio file
results = classifier("/Users/andreasblock/Desktop/Video-Emotion-Recognition/Audio/extracted_speech.wav")

# The output will be a list of dictionaries with labels and confidence scores
print("Whisper SER Results:")
for emotion in results:
    print(f"Emotion: {emotion['label']}, Confidence: {emotion['score']:.4f}")

# Example output:
# Emotion: Happy, Confidence: 0.8521
# Emotion: Neutral, Confidence: 0.1034