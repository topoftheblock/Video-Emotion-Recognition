# Use a lightweight Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and Lua script
COPY audio_sentence_app.py .
COPY audio_sentence.lua .

# Expose the port
EXPOSE 8000

# Command to run the FastAPI application
CMD ["uvicorn", "audio_sentence_app:app", "--host", "0.0.0.0", "--port", "8000"]