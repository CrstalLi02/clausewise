# Clausewise backend image
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies (pdfplumber needs some C libraries; extend separately for paddleocr)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

# Startup: run after dependencies are ready
CMD ["sh", "-c", "python -m scripts.wait_for_deps && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
