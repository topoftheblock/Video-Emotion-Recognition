from transformers import pipeline

# Initialize the pipeline with an IEMOCAP fine-tuned Wav2Vec 2.0 model
# "m3hrdadfi" maintains a widely used Wav2Vec2 model for IEMOCAP
classifier = pipeline(
    task="audio-classification", 
    model="m3hrdadfi/wav2vec2-base-100k-voxpopuli-iemocap",
    device=0 # Set to -1 if using CPU
)

# Run the classifier
results = classifier("/Users/andreasblock/Desktop/Video-Emotion-Recognition/Audio/extracted_speech.wav")

print("Conversational State (IEMOCAP) Results:")
for state in results:
    print(f"State: {state['label']}, Confidence: {state['score']:.4f}")

# Example output:
# State: Frustration, Confidence: 0.9210
# State: Angry, Confidence: 0.0512