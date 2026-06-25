FROM python:3.12-slim

# libgeos + libproj requis par shapely et pyproj
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-dev libproj-dev proj-data && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Répertoire de cache pour les PDF PLU téléchargés
RUN mkdir -p /data/pdfs
ENV PDF_CACHE_DIR=/data/pdfs

EXPOSE 8002
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8002}"]
