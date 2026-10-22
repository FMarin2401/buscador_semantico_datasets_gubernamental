# Buscador Semántico de Datasets Gubernamentales - Municipio de León

Plataforma de búsqueda inteligente, analítica y gestión de datos abiertos para el Municipio de León, Guanajuato. Utiliza modelos de procesamiento de lenguaje natural (NLP) y bases de datos vectoriales para ejecutar búsquedas semánticas densas, superando las limitaciones de la coincidencia léxica exacta ante lenguaje coloquial y modismos ciudadanos.

## Características Principales
* **Búsqueda Semántica Densa:** Transformación de consultas ciudadanas y metadatos en embeddings continuos para recuperar datasets según su contexto e intención real.
* **Pipeline de Ingesta Inteligente:** Automatización con IA (Google Gemini) para la extracción de esquemas, categorización por secretarías y generación estandarizada de metadatos.
* **Centro de Mando Administrativo:** Dashboard con métricas clave (KPIs), visualizaciones interactivas de distribución por dependencia y buzón ciudadano integrado.
* **Control de Acceso Basado en Roles (RBAC):** Autenticación JWT con expiración estricta y gestión de funcionarios (`admin` y `editor`) con contraseñas cifradas en Argon2.
* **Auditoría e Integridad Referencial:** Registro inmutable de eventos administrativos con descarga de reportes en CSV, borrado en cascada y prevención de registros huérfanos.
* **Exportación Dinámica Multiformato:** Conversión de datasets al vuelo desde CSV hacia JSON, XML y GeoJSON (detección automática de geometrías).
* **Arquitectura Vectorial y Relacional:** Persistencia híbrida mediante ChromaDB para la indexación semántica y SQLite/SQLAlchemy para auditoría, métricas y usuarios.

## Stack Tecnológico
* **Backend & API:** Python, FastAPI, Pandas, LXML.
* **Inteligencia Artificial & NLP:** Sentence Transformers (`intfloat/multilingual-e5-small`), Google Generative AI (Gemini).
* **Bases de Datos & Persistencia:** ChromaDB (Vectorial), SQLite con SQLAlchemy (Relacional).
* **Seguridad & Autenticación:** OAuth2 / JWT (PyJWT), pwdlib (Argon2).
* **Frontend:** HTML5 semántico, CSS3 (Mobile-First, Flexbox/Grid), Vanilla JavaScript (Arquitectura desacoplada sin frameworks pesados), Chart.js.

## Instalación y Ejecución

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/FMarin2401/buscador_semantico_datasets_gubernamental.git

2. Crear y activar el entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Configurar credenciales:
   Crear un archivo `.env` en la raíz del proyecto e inyectar la clave del modelo:
   ```text
   GEMINI_API_KEY=tu_api_key_aqui
   SECRET_KEY=tu_llave_secreta_jwt
   ADMIN_USER=admin_leon
   ADMIN_PASSWORD=tu_contraseña_segura
   LOG_LEVEL=DEBUG  # Opcional: INFO por defecto; DEBUG muestra el detalle de cada búsqueda
   GEMINI_MODEL=gemini-3.6-flash  # Opcional: modelo que usa scripts/analyze_csv.py
   ```

5. Iniciar el servidor local:
   ```bash
   uvicorn app.main:app 
   ```
   Al arrancar, la app aplica las migraciones pendientes de la base relacional con Alembic.

## Carga de datasets

Los datasets iniciales se cargan con un pipeline de tres pasos (las rutas están en `scripts/config_pipeline.py`):

1. Colocar los CSV del municipio en `data/entregados_municipio/` y generar sus metadatos con Gemini:
   ```bash
   python scripts/analyze_csv.py                  # Solo procesa los CSV nuevos
   python scripts/analyze_csv.py --solo-columnas  # Para archivos con datos personales: no envía filas a Google
   ```
2. **Revisar** `data/clean/catalogo_maestro_procesado.csv` (Gemini puede inventar dependencias o describir mal un dataset) y guardar la versión final como `data/clean/catalogo_maestro.csv`.
3. Indexar en ChromaDB:
   ```bash
   python scripts/migrate_chroma.py --simular  # Muestra qué cambiaría
   python scripts/migrate_chroma.py
   ```
   Se puede correr las veces que haga falta (por ejemplo, al cambiar de modelo de embeddings): no duplica datasets ni cambia sus IDs.

## Base de datos relacional (Alembic)

Para cambiar un modelo de `app/db_core/models.py`:
```bash
alembic revision --autogenerate -m "descripcion del cambio"  # Revisar el archivo generado en alembic/versions/
alembic upgrade head                                         # O simplemente reiniciar la app
```
Las bases creadas antes de Alembic se registran automáticamente como la revisión inicial (`0001`) la primera vez que arranca la app.

  ---
Desarrollado por [Francisco Marin Castillo](https://frankmarincas.dev/)
