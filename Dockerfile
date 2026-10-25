FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen

# Install system dependencies for media, document, and PDF conversions
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    poppler-utils \
    pandoc \
    libreoffice-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY cuttle/ ./cuttle/

RUN pip install --no-cache-dir .

# Create volume mount directory for batch file conversions
VOLUME ["/data"]

ENTRYPOINT ["cuttle"]
CMD ["--help"]
