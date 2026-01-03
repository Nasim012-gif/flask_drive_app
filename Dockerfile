FROM python:3.10-slim

# Install system dependencies for dlib and face-recognition (headless)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
# Install dlib first, then other packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir dlib>=19.24.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway sets this via $PORT)
EXPOSE 8080

# Run gunicorn with 1 worker to minimize memory usage
CMD gunicorn -w 1 -b 0.0.0.0:$PORT app:app \
    --timeout 300 \
    --worker-class sync \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --worker-tmp-dir /dev/shm
