# ---------------------------------------------------------------------------
# Production backend image for the Explaintool API.
#
# Multi-stage build:
#   stage 1 - install python dependencies (cached independently of source)
#   stage 2 - runtime image with the app, non-root user
# ---------------------------------------------------------------------------

# ---------- Stage 1: dependencies -------------------------------------------
FROM python:3.11-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System libraries required by document parsing / OCR dependencies
# (pymupdf, pdfplumber, Pillow, pytesseract).
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-hin \
        libgl1 \
        libglib2.0-0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY requirements.txt .
# Pre-build wheel layers so source changes do not reinstall dependencies.
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ---------- Stage 2: runtime -------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-hin \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create an unprivileged user to run the application.
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=deps /wheels /wheels
RUN pip install --no-index --find-links /wheels -r requirements.txt && rm -rf /wheels

# Application source (backend modules only; frontend is served by nginx).
COPY src/ ./src/

RUN mkdir -p /app/logs /app/data \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=3)"]

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
