FROM python:3.10

WORKDIR /usr/src/app

EXPOSE 9714

RUN DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install ffmpeg -y

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the model to cache it in the image
COPY model_preloader.py ./src/main/python/model_preloader.py
RUN python ./src/main/python/model_preloader.py

COPY TypeSystem.xml ./src/main/resources/TypeSystem.xml
COPY duui.py ./src/main/python/duui.py
COPY duui.lua ./src/main/lua/duui.lua

ARG DUUI_WHISPER_SER_LOG_LEVEL="DEBUG"
ENV DUUI_WHISPER_SER_LOG_LEVEL=$DUUI_WHISPER_SER_LOG_LEVEL

ARG DUUI_WHISPER_SER_ANNOTATOR_NAME="duui-whisper-ser"
ENV DUUI_WHISPER_SER_ANNOTATOR_NAME=$DUUI_WHISPER_SER_ANNOTATOR_NAME

ARG DUUI_WHISPER_SER_ANNOTATOR_VERSION="0.0.1"
ENV DUUI_WHISPER_SER_ANNOTATOR_VERSION=$DUUI_WHISPER_SER_ANNOTATOR_VERSION

ENTRYPOINT ["uvicorn", "src.main.python.duui:app", "--host", "0.0.0.0", "--port" ,"9714"]
CMD ["--workers", "1"]
