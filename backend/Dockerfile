FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa \
 && apt-get clean

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY datos/catalogo/ /app/datos/catalogo/

RUN useradd --create-home --uid 10001 qc && mkdir -p /datos/almacen && chown -R qc:qc /datos /app
USER qc
ENV STORAGE_DIR=/datos/almacen
EXPOSE 8000
# Aplica migraciones y arranca. Un solo proceso: el procesamiento corre en tareas de fondo.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
