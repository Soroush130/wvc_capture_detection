# Dockerfile
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:${PATH}"

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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python packages in separate steps for better debugging
RUN echo "=== Upgrading pip ===" \
    && pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch CPU version (not CUDA)
RUN echo "=== Installing PyTorch CPU ===" \
    && pip install --no-cache-dir \
        torch==2.1.2 \
        torchvision==0.16.2 \
        torchaudio==2.1.2 \
        --index-url https://download.pytorch.org/whl/cpu

# Install other requirements
RUN echo "=== Installing requirements.txt ===" \
    && pip install --no-cache-dir -r requirements.txt

# Verify critical packages are installed
RUN echo "=== Verifying installations ===" \
    && python -c "import celery; print(f'✅ Celery {celery.__version__}')" \
    && python -c "import telegram; print(f'✅ Telegram {telegram.__version__}')" \
    && python -c "import torch; print(f'✅ PyTorch {torch.__version__}')"

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/yolo_models /app/logs /tmp/wvc_photos

# Clean up
RUN rm -rf /root/.cache/pip \
    && find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -type f -name "*.pyc" -delete 2>/dev/null || true

CMD ["python", "-m", "celery", "-A", "celery_app", "worker", "--loglevel=info"]