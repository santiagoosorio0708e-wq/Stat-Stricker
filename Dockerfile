# ============================================================
# StatStriker - Dockerfile de producción / desarrollo local
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias primero para aprovechar caché de capas de Docker
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Código de la aplicación (sin .env ni storage/, excluidos en .dockerignore)
COPY backend ./backend
COPY data ./data
COPY frontend ./frontend

# Usuario sin privilegios y directorios persistentes
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/storage /home/appuser/.cache/chroma \
    && chown -R appuser:appuser /app /home/appuser/.cache

USER appuser

EXPOSE 8011

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8011/api/health', timeout=4)" || exit 1

# Inicializa SQLite/ChromaDB solo si la colección está vacía y arranca Uvicorn
CMD ["sh", "-c", "python -m backend.ingest --if-empty && exec uvicorn backend.main:app --host 0.0.0.0 --port 8011"]
