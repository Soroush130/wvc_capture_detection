# Dockerfile
# این Dockerfile در هر دو محیط (لوکال و سرور) استفاده می‌شود
# PyTorch خودش تشخیص می‌دهد GPU وجود دارد یا نه

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (better caching)
COPY requirements.txt .

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch with CUDA support (works on both CPU and GPU)
# اگر GPU نباشد، از CPU استفاده می‌کند
RUN pip install --no-cache-dir \
    torch==2.1.2 \
    torchvision==0.16.2 \
    torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cu121

# Install other Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /app/yolo_models /app/logs /tmp/wvc_photos

# Environment variables
ENV PYTHONUNBUFFERED=1

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]