# Dockerfile (optimized)
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and clean in ONE layer
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    git \
    curl \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

WORKDIR /app

COPY requirements.txt .

# Install ALL packages in ONE layer and clean immediately
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir \
        torch==2.1.2 \
        torchvision==0.16.2 \
        torchaudio==2.1.2 \
        --index-url https://download.pytorch.org/whl/cu121 \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip \
    && rm -rf /tmp/* /var/tmp/* \
    && find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -type f -name "*.pyc" -delete 2>/dev/null || true

COPY . .

RUN mkdir -p /app/yolo_models /app/logs /tmp/wvc_photos

ENV PYTHONUNBUFFERED=1

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]