# Use a standard Python image
FROM python:3.10-slim

# Install system dependencies required for audio processing (ffmpeg)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and Lua script
COPY src/main/python/voice_identity_app.py .
COPY src/main/lua/communication.lua .

# Expose the port Uvicorn will run on
EXPOSE 9714

# Set environment variable for HuggingFace Token (Required by pyannote)
# You should pass this when running the container: docker run -e HF_TOKEN="your_token" ...
ENV HF_TOKEN=""

# Command to run the FastAPI application
CMD ["uvicorn", "voice_identity_app:app", "--host", "0.0.0.0", "--port", "9714"]