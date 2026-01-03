FROM python:3.10-slim

# Install system dependencies for TensorFlow and DeepFace
RUN apt-get update && apt-get install -y \
    build-essential \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    libhdf5-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for TensorFlow
ENV TF_CPP_MIN_LOG_LEVEL=2
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
# Install TensorFlow 2.15.0 specifically (verified to exist)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir tensorflow==2.15.0 tf-keras==2.15.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway sets this via $PORT)
EXPOSE 8080

# Run gunicorn with 1 worker to minimize memory usage (optimized for Railway free tier)
CMD gunicorn -w 1 -b 0.0.0.0:$PORT app:app \
    --timeout 300 \
    --worker-class sync \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --worker-tmp-dir /dev/shm
