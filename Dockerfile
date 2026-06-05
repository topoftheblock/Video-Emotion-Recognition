FROM python:3.10

WORKDIR /usr/src/app

# Install system dependencies
RUN DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg

# Install python dependencies
COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Pre-download the model to cache it in the image (similar to crisper_whisper.py)
RUN python -c "from transformers import pipeline; pipeline('audio-classification', model='firdhokk/speech-emotion-recognition-with-openai-whisper-large-v3')"

# Copy the script and audio file
COPY ./Audio/extracted_speech.wav ./Audio/extracted_speech.wav
COPY ./Audio/Fine-Tuned\ Whisper.py ./Audio/Fine-Tuned\ Whisper.py

# Run the classifier script
CMD ["python", "-u", "./Audio/Fine-Tuned Whisper.py"]
