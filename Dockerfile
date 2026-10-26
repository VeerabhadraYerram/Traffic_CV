FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for OpenCV and PostgreSQL
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libpq-dev \
    gcc \
    g++ \
    cmake \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Run the stream analytics worker
CMD ["python", "worker.py"]
