# The importer: reads CAS files into the database and copies each one's
# companion video into the video store. Not a server — it runs, does the
# work, and exits.
#
# The build context is this directory. Everything the image needs is
# inside cas-to-postgres-importer/; nothing is pulled in from the rest
# of the project.
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The source root, and with it `resources/` — the three UIMA typesystem
# descriptors needed to read a CAS. Those are baked in rather than
# mounted: they belong to the pipeline version this image was built for,
# so shipping them together keeps the two in step. Override with the
# DUUI_TS_* variables and a mount to use different ones.
COPY src ./src

ENV PYTHONUNBUFFERED=1
# `src` is the source root rather than a package, so putting it on the
# path is what makes `import importer` resolve here and in the tests.
ENV PYTHONPATH=/app/src

# Input and output defaults, all overridable at run time. These are
# paths inside the container; what gets mounted onto them is a
# deployment decision.
ENV DUUI_INPUT_XMI_DIR=/data/input/xmi
ENV DUUI_INPUT_VIDEO_DIR=/data/input/videos
ENV DUUI_VIDEO_DIR=/data/videos

# Not root: a container running as root does not fail loudly, it
# silently does more than it should.
#
# /data/videos is created here and owned by the runner, so that a new
# named volume mounted over it inherits that ownership from the image.
# That is what lets a non-root importer write the videos it extracts.
RUN useradd --create-home --uid 1000 runner \
    && mkdir -p /data/videos \
    && chown -R runner:runner /data/videos
USER runner

# Arguments are paths, any mix of files and directories. With none,
# everything in DUUI_INPUT_XMI_DIR is imported.
ENTRYPOINT ["python", "-m", "importer"]
