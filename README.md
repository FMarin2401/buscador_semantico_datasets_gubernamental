# Buscador Semántico de Datasets Gubernamentales - Municipio de León

Plataforma de búsqueda inteligente, analítica y gestión de datos abiertos para el Municipio de León, Guanajuato. Utiliza modelos de procesamiento de lenguaje natural (NLP) y bases de datos vectoriales para ejecutar búsquedas semánticas densas, superando las limitaciones de la coincidencia léxica exacta ante lenguaje coloquial y modismos ciudadanos.

## Características Principales
* **Búsqueda Semántica Densa:** Transformación de consultas ciudadanas y metadatos en embeddings continuos para recuperar datasets según su contexto e intención real.
* **Pipeline de Ingesta Inteligente:** Automatización con IA (Google Gemini) para la extracción de esquemas, categorización por secretarías y generación estandarizada de metadatos.
* **Centro de Mando Administrativo:** Dashboard con métricas clave (KPIs), visualizaciones interactivas de distribución por dependencia y buzón ciudadano integrado.
* **Control de Acceso Basado en Roles (RBAC):** Autenticación JWT con expiración estricta y gestión de funcionarios (`admin` y `editor`) con contraseñas cifradas en bcrypt.
* **Auditoría e Integridad Referencial:** Registro inmutable de eventos administrativos con descarga de reportes en CSV, borrado en cascada y prevención de registros huérfanos.
* **Exportación Dinámica Multiformato:** Conversión de datasets al vuelo desde CSV hacia JSON, XML y GeoJSON (detección automática de geometrías).
* **Arquitectura Vectorial y Relacional:** Persistencia híbrida mediante ChromaDB para la indexación semántica y SQLite/SQLAlchemy para auditoría, métricas y usuarios.

## Stack Tecnológico
* **Backend & API:** Python, FastAPI, Pandas, LXML.
* **Inteligencia Artificial & NLP:** Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`), Google Generative AI (Gemini).
* **Bases de Datos & Persistencia:** ChromaDB (Vectorial), SQLite con SQLAlchemy (Relacional).
* **Seguridad & Autenticación:** OAuth2 / JWT (PyJWT), Passlib (Bcrypt).
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
   ```

5. Iniciar el servidor local:
   ```bash
   uvicorn app.main:app 
   ```
  Accede a la plataforma en: http://127.0.0.1:8000
  Documentación interactiva de la API (Swagger UI): http://127.0.0.1:8000/docs