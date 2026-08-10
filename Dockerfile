FROM python:3.11-slim

# Prevent interactive prompts during apt package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update apt source list and install system dependencies with cleanup
RUN apt-get update --fix-missing && \
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

# Run FastAPI app with Gunicorn
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:10000"]