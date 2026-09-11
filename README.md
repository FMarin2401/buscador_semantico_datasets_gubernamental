# Buscador Semántico De Datasets Gubernamental - Prototipo Municipio de León

Plataforma de búsqueda inteligente y gestión de datasets abiertos para el Municipio de León, Guanajuato. Utiliza modelos de procesamiento de lenguaje natural (NLP) para ejecutar búsquedas semánticas, superando las limitaciones de las consultas tradicionales por coincidencias exactas.

## Características Principales
* **Búsqueda Semántica:** Integración de embeddings matemáticos para devolver conjuntos de datos basados en la intención y el contexto del ciudadano.
* **Pipeline de Ingesta Automatizado:** Scripts para análisis masivo de CSVs, clasificación automática de dependencias mediante IA y generación de metadatos.
* **Exportación Dinámica (API):** Conversión de datasets en tiempo real desde CSV hacia JSON, XML y GeoJSON.
* **Arquitectura Vectorial:** Implementación de ChromaDB para almacenamiento de alta dimensión y consulta eficiente de similitud.

## Stack Tecnológico
* **Core & Backend:** Python, FastAPI, Pandas, LXML.
* **Inteligencia Artificial:** Sentence Transformers, Google Generative AI (Modelos Flash).
* **Almacenamiento:** ChromaDB (Base de datos vectorial).
* **Frontend:** HTML5, CSS3, Vanilla JavaScript.

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