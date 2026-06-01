from funasr import AutoModel

# Load the SenseVoice-Small model
# You can change device="cuda:0" to device="cpu" if you don't have a GPU
model = AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model="fsmn-vad", # Voice Activity Detection splits long audio
    device="cuda:0" 
)

# Run inference on your audio file
# Language="auto" allows it to automatically detect English, Chinese, etc.
result = model.generate(
    input="/Users/andreasblock/Desktop/Video-Emotion-Recognition/Audio/extracted_speech.wav",
    language="auto",
    use_itn=True # Includes punctuation formatting
)

# The output is a list containing a dictionary with the transcribed text and tags
print("Transcription and Emotion Tags:")
print(result[0]["text"])

# Example output: "Oh, what a brilliant idea [😡 Angry] [😀 Laughter]"