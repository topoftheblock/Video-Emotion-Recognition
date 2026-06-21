# Use a lightweight Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and Lua script
COPY src/main/python/audio_sentence_app.py .
COPY src/main/lua/audio_sentence.lua .

# Expose the port
EXPOSE 9714

# Command to run the FastAPI application
CMD ["uvicorn", "audio_sentence_app:app", "--host", "0.0.0.0", "--port", "9714"]