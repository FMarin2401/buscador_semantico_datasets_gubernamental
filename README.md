# Buscador Semántico de Datasets Gubernamentales - Municipio de León

Plataforma de búsqueda inteligente, analítica y gestión de datos abiertos para el Municipio de León, Guanajuato. Utiliza modelos de procesamiento de lenguaje natural (NLP) y bases de datos vectoriales para ejecutar búsquedas semánticas densas, superando las limitaciones de la coincidencia léxica exacta ante lenguaje coloquial y modismos ciudadanos.

## Características Principales
* **Búsqueda Semántica Densa:** Transformación de consultas ciudadanas y metadatos en embeddings continuos para recuperar datasets según su contexto e intención real.
* **Pipeline de Ingesta Inteligente:** Automatización con IA (Google Gemini) para la extracción de esquemas, categorización por secretarías y generación estandarizada de metadatos.
* **Centro de Mando Administrativo:** Dashboard con métricas clave (KPIs), visualizaciones interactivas de distribución por dependencia y buzón ciudadano integrado.
* **Control de Acceso Basado en Roles (RBAC):** Autenticación JWT con expiración estricta y gestión de funcionarios (`admin` y `editor`) con contraseñas cifradas en Argon2.
* **Auditoría e Integridad Referencial:** Registro inmutable de eventos administrativos con descarga de reportes en CSV, borrado en cascada y prevención de registros huérfanos.
* **Exportación Dinámica Multiformato:** Conversión de datasets al vuelo desde CSV hacia JSON, XML y GeoJSON (detección automática de geometrías).
* **Arquitectura Vectorial y Relacional:** Persistencia híbrida mediante ChromaDB para la indexación semántica y PostgreSQL (SQLAlchemy + Alembic) para auditoría, métricas y usuarios.

## Stack Tecnológico
* **Backend & API:** Python, FastAPI, Pandas, LXML.
* **Inteligencia Artificial & NLP:** Sentence Transformers (`intfloat/multilingual-e5-small`), Google Generative AI (Gemini).
* **Bases de Datos & Persistencia:** ChromaDB (vectorial), PostgreSQL 16 con SQLAlchemy y Alembic (relacional).
* **Seguridad & Autenticación:** OAuth2 / JWT (PyJWT), pwdlib (Argon2).
* **Frontend:** HTML5 semántico, CSS3 (Mobile-First, Flexbox/Grid), Vanilla JavaScript, Chart.js, servido con nginx.
* **Contenedores:** Docker Compose con tres servicios (frontend, API y base de datos).

## Arquitectura en contenedores

| Servicio | Imagen | Función | Puerto en tu computadora |
|---|---|---|---|
| `frontend` | nginx (`frontend/Dockerfile`) | Sirve las páginas y reenvía `/api`, `/docs`, `/redoc` y `/openapi.json` a la API | **8080** |
| `api` | Python 3.12 (`api/Dockerfile`) | FastAPI, modelo de embeddings y ChromaDB | ninguno (red interna) |
| `db` | `postgres:16` | Usuarios, datasets, reportes, bitácora, descargas y mensajes | ninguno (red privada) |

La base de datos está en una red interna a la que solo llega la API: ni el navegador ni el frontend pueden conectarse a ella.

## Estructura del repositorio

```
├── frontend/            # Páginas (plantillas Jinja2), CSS, JS, nginx.conf y Dockerfile
├── api/                 # Backend FastAPI
│   ├── app/             # Código de la API (rutas en app/api/, modelos en app/db_core/)
│   ├── alembic/         # Migraciones de la base relacional
│   ├── scripts/         # Ingesta con Gemini, indexación en ChromaDB y evaluación
│   ├── eval/            # Conjunto de evaluación del buscador
│   ├── tests/           # Pruebas automatizadas (pytest)
│   └── Dockerfile
├── db/
│   ├── seed/            # Datos de ejemplo: catálogo revisado y 75 CSV del municipio
│   └── objetos_bd.sql   # Índice y vista de PostgreSQL, con su justificación
├── docs/                # Documentación técnica y solicitudes de cambio (SC-001)
├── docker-compose.yml
├── Dockerfile.azure     # Imagen de un solo contenedor para Azure Container Apps
└── .env.example
```

## Instalación y ejecución

### Requisitos

Solo **Docker Desktop** (abierto y en ejecución). No hace falta instalar Python, PostgreSQL ni nada más.

### Pasos

1. Copiar el archivo de variables de ejemplo:
   ```bash
   cp .env.example .env        # En Windows (PowerShell): Copy-Item .env.example .env
   ```
   Los valores de ejemplo funcionan tal cual para correrlo en local.

2. Construir y levantar los tres contenedores:
   ```bash
   docker compose up --build
   ```
   **El primer build tarda entre 15 y 20 minutos** (medido en una copia limpia): descarga PyTorch (~800 MB) y el modelo de embeddings. No está colgado; los siguientes arranques toman segundos. La aplicación está lista cuando el comando muestra `Container ...-frontend-1 Started` y los logs de la API dicen `Application startup complete`.

3. Abrir la aplicación:

   | Qué | URL |
   |---|---|
   | Aplicación web | http://localhost:8080 |
   | Documentación interactiva de la API (Swagger) | http://localhost:8080/docs |
   | Documentación alternativa (ReDoc) | http://localhost:8080/redoc |
   | Especificación OpenAPI | http://localhost:8080/openapi.json |
   | Panel de administración | http://localhost:8080/login.html (usuario y contraseña de `ADMIN_USER` y `ADMIN_PASSWORD` en `.env`) |

### Cómo se cargan los datos de ejemplo

Todo ocurre al arrancar, sin pasos manuales:

1. **PostgreSQL:** la API aplica las migraciones de Alembic (crea las tablas) y registra el administrador inicial con `ADMIN_USER` y `ADMIN_PASSWORD`.
2. **Datasets:** antes de iniciar la API, el contenedor ejecuta `scripts/migrate_chroma.py`, que indexa en ChromaDB los 75 datasets de `db/seed/` (catálogo revisado y sus CSV). El script es idempotente: en los arranques siguientes no duplica nada.

Los datos se guardan en volúmenes de Docker (`pgdata`, `chroma` y `raw`), así que sobreviven a reinicios.

### Detener y reiniciar

```bash
docker compose stop            # Detiene los contenedores (o Ctrl+C si está en primer plano)
docker compose start           # Los vuelve a iniciar con los mismos datos
docker compose down            # Detiene y borra los contenedores; los datos se conservan
docker compose up -d           # Levanta todo en segundo plano
docker compose logs -f api     # Ver los logs de la API
docker compose down -v         # Borra también los volúmenes: el siguiente "up" empieza desde los datos de ejemplo
```

### Problemas comunes

| Síntoma | Solución |
|---|---|
| `Cannot connect to the Docker daemon` / `error during connect` | Docker Desktop no está abierto. Ábrelo, espera a que diga *Engine running* y repite el comando. |
| `port is already allocated` / `Bind for 0.0.0.0:8080 failed` | Otro programa usa el puerto 8080. Cambia `PUERTO_WEB` (y `ALLOWED_ORIGINS`) en `.env`, por ejemplo a `8081`, y entra a http://localhost:8081. |
| El navegador no carga justo después del `up` | El frontend espera a que la API termine de cargar el modelo (hasta ~1 min tras el build). Revisa `docker compose ps`: `api` debe estar `healthy`. |
| `env file .env not found` | Falta el paso 1: copiar `.env.example` a `.env`. |
| `ADMIN_USER y ADMIN_PASSWORD deben estar configuradas` en los logs | El `.env` no tiene esas variables. Cópialas de `.env.example`. |
| No puedo entrar al panel tras cambiar `ADMIN_PASSWORD` | El administrador solo se crea en el primer arranque. Para empezar de cero: `docker compose down -v` y `docker compose up --build`. |
| El build parece detenido en `pip install` | Es normal la primera vez: descarga PyTorch y otras librerías grandes (15 a 20 minutos en total). |
| El build falla al descargar paquetes o el modelo | Requiere internet. Vuelve a ejecutar `docker compose up --build`: Docker reanuda desde la última capa completa. |

## Pruebas automatizadas

Con la aplicación levantada:

```bash
docker compose exec api pytest
```

Ejecuta la suite de `api/tests/` (60 pruebas) en una base temporal, sin tocar los datos de la aplicación. Incluye las reglas de negocio y sus pruebas negativas, por ejemplo reabrir un reporte resuelto (`409`) o publicar dos veces el mismo archivo (`409`).

## Desarrollo sin Docker (opcional)

```bash
python -m venv venv && source venv/bin/activate   # En Windows: venv\Scripts\activate
pip install -r api/requirements.txt
cd api
python scripts/migrate_chroma.py   # Indexa db/seed en api/data/chroma_db
uvicorn app.main:app               # http://localhost:8000, con SQLite en api/data/usuarios.db
```

Sin `DATABASE_URL`, la API usa SQLite y sirve también el frontend (desde `../frontend`). Lee el mismo `.env` de la raíz.

## Carga de datasets nuevos

Los datasets se cargan con un pipeline de tres pasos (rutas en `api/scripts/config_pipeline.py`), desde la carpeta `api/`:

1. Colocar los CSV del municipio en `db/seed/csv/` y generar sus metadatos con Gemini (requiere `GEMINI_API_KEY`):
   ```bash
   python scripts/analyze_csv.py                  # Solo procesa los CSV nuevos
   python scripts/analyze_csv.py --solo-columnas  # Para archivos con datos personales: no envía filas a Google
   ```
2. **Revisar** `api/data/clean/catalogo_maestro_procesado.csv` (Gemini puede inventar dependencias o describir mal un dataset) y guardar la versión final como `db/seed/catalogo_maestro.csv`.
3. Indexar en ChromaDB:
   ```bash
   python scripts/migrate_chroma.py --simular  # Muestra qué cambiaría
   python scripts/migrate_chroma.py
   ```
   En Docker basta con `docker compose up --build`: el contenedor de la API corre este paso al arrancar.

## Base de datos relacional (Alembic)

Para cambiar un modelo de `api/app/db_core/models.py`, desde `api/`:
```bash
alembic revision --autogenerate -m "descripcion del cambio"  # Revisar el archivo generado en alembic/versions/
alembic upgrade head                                         # O simplemente reiniciar la app
```

## Despliegue en Azure

La demo pública usa un solo contenedor con SQLite (`Dockerfile.azure`). Los detalles están en la sección 15 de [la documentación técnica](docs/Documentación_Técnica_Buscador.md).

  ---
Desarrollado por [Francisco Marin Castillo](https://frankmarincas.dev/)
