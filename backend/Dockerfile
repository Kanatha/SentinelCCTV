FROM python:3.11-slim

# avoid interactive prompts, ensure logs are unbuffered
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# install ffmpeg and minimal libs needed by opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy only requirements first to leverage Docker layer cache
COPY requirements.txt /app/requirements.txt

# upgrade pip and install python deps
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# copy app code
COPY . /app

# create a non-root user and chown the app dir
RUN useradd -m appuser && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

# Ensure this matches your actual server filename
CMD ["python", "server.py"]
