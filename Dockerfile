FROM python:3.11-slim

# Prevent interactive prompts during apt package installation
ENV DEBIAN_FRONTEND=noninteractive

# Configure apt to retry on network stalls and use clean mirror lists
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80retries && \
    apt-get clean && \
    apt-get update -o Acquire::CompressionTypes::Order::=gz --fix-missing && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libtesseract-dev \
        libgl1-mesa-glx \
        libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Run FastAPI app with Gunicorn (1 worker, 2 threads to keep memory footprint under 512MB)
CMD ["gunicorn", "-w", "1", "--threads", "2", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:10000"]