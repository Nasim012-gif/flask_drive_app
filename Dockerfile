FROM python:3.10-slim

# Install system dependencies needed for face-recognition and dlib
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
# Install dlib first (it's a dependency of face-recognition)
RUN pip install --no-cache-dir dlib==19.24.0

# Then install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway sets this via $PORT)
EXPOSE 8080

# Run gunicorn with higher timeout for face processing
CMD gunicorn -w 4 -b 0.0.0.0:$PORT app:app --timeout 300 --worker-class sync
