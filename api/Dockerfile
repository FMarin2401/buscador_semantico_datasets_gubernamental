# Imagen de la API para docker compose: solo el backend. El frontend va en su propio contenedor (frontend/Dockerfile)
# y la base de datos en PostgreSQL. La imagen de Azure, con todo en un contenedor, es ../Dockerfile.azure.
FROM python:3.12-slim

# Evitar que Python escriba archivos .pyc y forzar salida de logs inmediata en consola
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar librerías y LXML (curl lo usa el healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar requirements primero
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Precargar el modelo de Hugging Face en la imagen para arranque inmediato
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

# Datos de ejemplo (db/seed): catálogo revisado y CSV del municipio. Llegan como contexto adicional "seed"
# desde docker-compose.yml, porque viven fuera de esta carpeta
COPY --from=seed . /app/seed/
ENV CARPETA_ORIGINALES=/app/seed/csv/ \
    CATALOGO_REVISADO=/app/seed/catalogo_maestro.csv

# Copiar el resto del código del proyecto
COPY . .

EXPOSE 8000

# Indexa la semilla (idempotente: en el primer arranque carga los datasets y después no duplica nada) y arranca la API.
# La IP del rate limit la toma app/limiter.py del último valor de X-Forwarded-For, el que agrega nginx.
CMD ["sh", "-c", "python scripts/migrate_chroma.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*"]
