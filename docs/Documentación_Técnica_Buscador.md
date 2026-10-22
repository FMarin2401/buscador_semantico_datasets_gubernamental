# Documentación Técnica Buscador Semántico de Datasets Gubernamentales

**Proyecto:** Portal de Datos Abiertos del Municipio de León, Guanajuato
**Autor:** [Francisco Marin Castillo](https://frankmarincas.dev/)
**Repositorio:** https://github.com/FMarin2401/buscador_semantico_datasets_gubernamental
**Última actualización:** 2026-10-22

---
	
## Índice

1. [Descripción general](#1-descripción-general)
2. [Arquitectura](#2-arquitectura)
3. [Estructura del repositorio](#3-estructura-del-repositorio)
4. [Configuración y variables de entorno](#4-configuración-y-variables-de-entorno)
5. [Instalación y ejecución](#5-instalación-y-ejecución)
6. [Motor de búsqueda semántica](#6-motor-de-búsqueda-semántica)
7. [Persistencia de datos](#7-persistencia-de-datos)
8. [Referencia de la API](#8-referencia-de-la-api)
9. [Autenticación y control de acceso](#9-autenticación-y-control-de-acceso)
10. [Gestión de datasets](#10-gestión-de-datasets)
11. [Frontend](#11-frontend)
12. [Scripts de ingesta y evaluación](#12-scripts-de-ingesta-y-evaluación)
13. [Seguridad](#13-seguridad)
14. [Monitoreo y logging](#14-monitoreo-y-logging)
15. [Despliegue con Docker](#15-despliegue-con-docker)
16. [Historial de problemas resueltos](#16-historial-de-problemas-resueltos)
17. [Problemas conocidos y trabajo futuro](#17-problemas-conocidos-y-trabajo-futuro)

---

## 1. Descripción general

El proyecto es un portal web de datos abiertos con un **buscador semántico**. Encuentra conjuntos de datos (datasets) municipales a partir de consultas en lenguaje natural y coloquial, por ejemplo *"¿dónde tiro mis teles viejas?"* o *"se fundió el foco de la calle"*. No exige que la consulta contenga las palabras exactas del título del dataset.

Para lograrlo, convierte tanto las consultas como los metadatos de cada dataset en **embeddings** (vectores densos) y compara su similitud coseno en una base de datos vectorial.

### Capacidades principales

| Área           | Funcionalidad                                                                                                                                             |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ciudadanía     | Búsqueda semántica, exploración del catálogo con filtros, descarga en CSV/JSON/XML/GeoJSON, formulario de contacto                                        |
| Administración | Dashboard con KPIs y gráficas, publicación, edición y eliminación de datasets, buzón ciudadano, gestión de funcionarios, bitácora de auditoría exportable |
| Ingesta        | Generación automática de metadatos (título, descripción, dependencia, categoría) con Google Gemini, revisión humana y carga idempotente a ChromaDB         |
| Calidad        | Evaluación contra un *ground truth* de 100 consultas (Recall@1/5/10, MRR) y 30 consultas fuera de tema; comparación de modelos de embeddings             |

### Stack tecnológico

| Capa            | Tecnología                                                                     |
| --------------- | ------------------------------------------------------------------------------ |
| API             | Python 3.12, FastAPI, Uvicorn, Starlette                                       |
| NLP             | Sentence Transformers (`intfloat/multilingual-e5-small`), PyTorch (CPU)        |
| IA generativa   | Google Gemini (`google-genai`) — solo en el script de ingesta                  |
| Base vectorial  | ChromaDB (cliente persistente, métrica coseno, índice HNSW)                    |
| Base relacional | SQLAlchemy 2 + Alembic — SQLite en local / PostgreSQL en producción            |
| Seguridad       | PyJWT (JWT HS256), pwdlib + Argon2, SlowAPI (rate limiting)                    |
| Procesamiento   | Pandas, LXML                                                                   |
| Frontend        | HTML5, CSS3, JavaScript sin frameworks, Jinja2 (servido por FastAPI), Chart.js |
| Infraestructura | Docker, Docker Compose                                                         |

---

## 2. Arquitectura

```mermaid
flowchart LR
    subgraph Cliente
        U[Ciudadano] --> FE[Frontend HTML/JS]
        A[Funcionario] --> FE
    end

    FE -->|HTTP / JSON| API[FastAPI<br/>app/main.py]

    subgraph Backend
        API --> R1[search.py]
        API --> R2[manipulate_datasets.py]
        API --> R3[auth.py / users.py]
        API --> R4[contact.py]
        API --> R5[pages.py]
        R1 & R2 --> NLP[nlp_model.py<br/>multilingual-e5-small]
        R1 & R2 --> CH[(ChromaDB<br/>data/chroma_db)]
        R1 & R2 & R3 & R4 --> SQL[(SQLite / PostgreSQL)]
        R2 --> FS[(Archivos CSV<br/>data/raw)]
    end

    subgraph Ingesta offline
        CSV[data/entregados_municipio] --> S1[analyze_csv.py] -->|Gemini| CATG[catalogo_maestro_procesado.csv]
        CATG -->|revisión humana| CAT[catalogo_maestro.csv]
        CAT --> S2[migrate_chroma.py] --> CH
        S2 --> FS
    end
```

### Persistencia híbrida

- **ChromaDB** guarda el índice semántico: el ID, el título, el embedding y los metadatos de cada dataset. Es la **fuente de verdad del catálogo**.
- **La base relacional** guarda usuarios, mensajes de contacto, la bitácora de auditoría y los contadores de descargas. Su esquema se versiona con **Alembic**.
- **El sistema de archivos** (`data/raw/{id}.csv`) guarda los archivos CSV originales. El nombre de cada archivo es el ID del dataset en ChromaDB.

### Ciclo de vida de la aplicación (`lifespan`)

Al arrancar, `app/main.py` hace lo siguiente:

1. **Aplica las migraciones** de Alembic (`aplicar_migraciones()` en `app/db_core/migraciones.py`). Si la base ya tiene tablas pero no tiene control de versiones (bases creadas antes de Alembic con `create_all`), la registra automáticamente como la revisión inicial `0001`.
2. Si la tabla `usuarios` está vacía, crea un administrador inicial con `ADMIN_USER` y `ADMIN_PASSWORD`. Si faltan esas variables, el arranque falla.
3. **Comprueba la compatibilidad del índice**: compara el modelo con que se indexó ChromaDB (metadato `modelo_embeddings` de la colección) con el que usa la app. Si no coinciden, marca `app_state["modelo_compatible"] = False` y lo registra como error (ver [6. Protección contra índices incompatibles](#protección-contra-índices-incompatibles)).
4. Ejecuta un **warm-up**: genera un embedding de prueba y lanza una consulta a ChromaDB para cargar el modelo y el índice en RAM. Si funciona, marca `app_state["warmup_ready"] = True`.

El *readiness probe* solo responde `200` cuando el warm-up terminó, el índice es compatible y la base relacional responde.

---

## 3. Estructura del repositorio

```
buscador_semantico_datasets_gubernamental/
├── app/
│   ├── main.py                  # App FastAPI, lifespan, middlewares (CSP), CORS, health checks
│   ├── nlp_model.py             # Modelo e5, prefijos query/passage, umbral de distancia
│   ├── db_chroma.py             # Cliente ChromaDB y helpers (buscar, listar, guardar, upsert, modelo indexado)
│   ├── security.py              # Cifrado y verificación de contraseñas (Argon2, migración de bcrypt)
│   ├── limiter.py               # Instancia de SlowAPI (rate limit por IP)
│   ├── db_core/
│   │   ├── connection.py        # Engine SQLAlchemy (SQLite/PostgreSQL), SessionLocal, get_db
│   │   ├── migraciones.py       # Aplica las migraciones de Alembic al arrancar
│   │   └── models.py            # Modelos ORM
│   └── api/
│       ├── search.py            # /api/buscar, /api/catalogos
│       ├── manipulate_datasets.py # CRUD de datasets, descargas, bitácora
│       ├── auth.py              # Login/logout JWT, dependencias de autorización
│       ├── users.py             # Gestión de funcionarios
│       ├── contact.py           # Buzón ciudadano
│       └── pages.py             # Rutas que sirven las páginas HTML
├── alembic/                     # Migraciones de la base relacional (versions/0001_esquema_inicial.py)
├── alembic.ini
├── frontend/
│   ├── *.html                   # Páginas (plantillas Jinja2)
│   ├── css/style.css            # Estilos Mobile-First
│   ├── js/                      # Lógica de cliente por página
│   └── assets/                  # Logo y favicon
├── scripts/
│   ├── config_pipeline.py       # Rutas y categorías oficiales compartidas por la ingesta
│   ├── analyze_csv.py           # Generación de metadatos con Gemini
│   ├── migrate_chroma.py        # Carga idempotente del catálogo a ChromaDB
│   ├── evaluate_model.py        # Evaluación: Recall@k, MRR, consultas fuera de tema, calibración del umbral
│   └── comparar_modelos.py      # Comparación de modelos de embeddings sin modificar ChromaDB
├── eval/
│   ├── ground_truth.json        # 100 consultas coloquiales con su dataset esperado
│   ├── consultas_fuera_de_tema.json # 30 consultas que ningún dataset debería responder
│   ├── resultados/              # Métricas en JSON (baseline, comparación, e5_small)
│   └── experimentos/            # Documentación de cada experimento
├── docs/                        # Esta documentación y la revisión de código
├── data/                        # (ignorado por git) chroma_db, raw, clean, entregados_municipio, usuarios.db
├── logs/                        # (ignorado por git) auditoria.log
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 4. Configuración y variables de entorno

Las variables se leen del archivo `.env` en la raíz del proyecto. Ese archivo está excluido de git y de la imagen Docker.

| Variable | Obligatoria | Descripción | Valor por defecto |
|---|---|---|---|
| `SECRET_KEY` | **Sí** | Clave para firmar los JWT. Sin ella, la app no arranca. | — |
| `ADMIN_USER` | Sí, en el primer arranque | Usuario del administrador inicial | — |
| `ADMIN_PASSWORD` | Sí, en el primer arranque | Contraseña del administrador inicial | — |
| `GEMINI_API_KEY` | Solo para `analyze_csv.py` | API key de Google Gemini | — |
| `GEMINI_MODEL` | No | Modelo de Gemini que usa `analyze_csv.py` | `gemini-3.6-flash` |
| `ALLOWED_ORIGINS` | No | Orígenes CORS permitidos, separados por comas | `http://localhost:8000` |
| `DATABASE_URL` | No | URL de PostgreSQL. Si no se define, se usa SQLite en `data/usuarios.db` | — |
| `ENVIRONMENT` | No | Con el valor `production`, la cookie de sesión lleva el flag `Secure` | `local` |
| `LOG_LEVEL` | No | Nivel de logging. `DEBUG` registra el detalle de cada búsqueda | `INFO` |

Ejemplo:

```env
GEMINI_API_KEY=tu_api_key
SECRET_KEY=una_cadena_larga_y_aleatoria
ADMIN_USER=admin_leon
ADMIN_PASSWORD=contraseña_segura
ALLOWED_ORIGINS=http://localhost:8000
# DATABASE_URL=postgresql://usuario:pass@host:5432/portal
# ENVIRONMENT=production
# LOG_LEVEL=DEBUG
```

> Para generar una `SECRET_KEY` segura: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

---

## 5. Instalación y ejecución

### Local

```bash
git clone https://github.com/FMarin2401/buscador_semantico_datasets_gubernamental.git
cd buscador_semantico_datasets_gubernamental

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt   # Incluye torch para CPU desde el índice de PyTorch

# Crear el archivo .env (ver sección 4)

uvicorn app.main:app --reload
```

La aplicación queda disponible en `http://localhost:8000`, y la documentación interactiva de la API en `http://localhost:8000/docs` (Swagger) y `http://localhost:8000/redoc`.

Al arrancar, la app crea o actualiza las tablas relacionales con Alembic; no hace falta ningún paso manual. ChromaDB crea `data/chroma_db` automáticamente.

### Carga inicial del catálogo

Si arrancas con una base vectorial vacía, consulta la sección [12. Scripts](#12-scripts-de-ingesta-y-evaluación) para poblarla desde los CSV del municipio. También puedes publicar datasets uno por uno desde el panel de administración.

### Cambios en el esquema de la base relacional

```bash
alembic revision --autogenerate -m "descripcion del cambio"  # Revisar el archivo generado en alembic/versions/
alembic upgrade head                                         # O simplemente reiniciar la app
```

---

## 6. Motor de búsqueda semántica

### Modelo

- **`intfloat/multilingual-e5-small`** (Sentence Transformers): multilingüe, genera vectores de **384 dimensiones** y ocupa lo mismo que el modelo anterior (`paraphrase-multilingual-MiniLM-L12-v2`).
- Se eligió comparando cuatro modelos contra el *ground truth*: sube el Recall@5 de **78 % a 95 %** (ver `eval/experimentos/2026-10-21_comparacion_modelos.md` y `2026-10-22_implementacion_e5.md`).
- Se carga una sola vez al importar `app/nlp_model.py`, y la imagen Docker lo descarga durante el build.

### Prefijos `query:` y `passage:`

Los modelos e5 se entrenaron con prefijos, y sin ellos rinden bastante peor. `app/nlp_model.py` expone funciones separadas para que ningún punto del código pueda olvidarlos:

| Función | Prefijo | Uso |
|---|---|---|
| `generar_embedding_consulta(texto)` / `generar_embeddings_consultas(lista)` | `"query: "` | Búsquedas de la ciudadanía y evaluación |
| `generar_embedding_documento(texto)` / `generar_embeddings_documentos(lista)` | `"passage: "` | Textos de los datasets que se indexan |

Los vectores se normalizan (`normalize_embeddings=True`).

### Texto indexado

Cada dataset se representa con este texto compuesto, generado por `texto_para_indexar()` (lo comparten el panel y `migrate_chroma.py`):

```
"{titulo}. {descripcion} Dependencia: {dependencia}"
```

En ChromaDB, el campo `document` guarda solo el **título**. El embedding, en cambio, se calcula con el texto compuesto completo (con el prefijo `passage: `).

### Flujo de una búsqueda (`GET /api/buscar`)

1. Genera el embedding del `prompt` del usuario (con el prefijo `query: `).
2. Consulta ChromaDB por los **10 vecinos más cercanos** (distancia coseno, índice HNSW).
3. Filtra los resultados con un **umbral de distancia ≤ 0.19** (`UMBRAL_DISTANCIA` en `app/nlp_model.py`). Los que lo superan se descartan por baja relevancia.
4. Agrega a cada resultado su contador de descargas, consultando solo los IDs que se devuelven.
5. Devuelve los resultados ordenados por cercanía.

### Calibración del umbral

Cada modelo tiene su propia escala de distancias: e5 concentra casi todo entre 0.10 y 0.25, mientras que MiniLM llegaba hasta 1.0. Por eso el umbral vive junto al modelo y **hay que recalibrarlo si se cambia de modelo**:

```bash
python scripts/evaluate_model.py --calibrar
```

El valor 0.19 equilibra los aciertos visibles (89 % de las consultas muestran el dataset correcto en el Top-5) con el rechazo de consultas ajenas (83 % de las 30 consultas fuera de tema no devuelven resultados).

### Protección contra índices incompatibles

MiniLM y e5-small generan vectores del **mismo tamaño**, así que si la app usa un modelo y ChromaDB se indexó con otro, **no hay ningún error visible**: la búsqueda simplemente compara vectores incompatibles y devuelve resultados sin sentido. Para evitarlo:

- `migrate_chroma.py` guarda el nombre del modelo en el metadato `modelo_embeddings` de la colección.
- Al arrancar, la app lo compara con `NOMBRE_MODELO`. Si no coinciden, el *readiness probe* responde `503` con el mensaje *"La base vectorial se indexó con otro modelo de embeddings; hay que re-indexarla"*.
- Una colección vacía se marca con el modelo actual al arrancar, para que los datasets que se agreguen desde el panel queden registrados correctamente.

### Enriquecimiento de descripciones

El script de ingesta pide a Gemini que incluya en la descripción **sinónimos y palabras clave** que la ciudadanía suele usar ("teléfono", "horarios", "citas"…). Esto acerca el vocabulario coloquial al de los metadatos oficiales y mejora el recall.

---

## 7. Persistencia de datos

### 7.1 ChromaDB — colección `datasets_gobierno`

| Campo | Contenido |
|---|---|
| `id` | UUID del dataset (también es el nombre del archivo en `data/raw/`). `uuid4` para los subidos desde el panel; `uuid5` determinista para los cargados con `migrate_chroma.py`. Los datasets ya indexados conservan su ID al re-indexar |
| `document` | Título del dataset |
| `embedding` | Vector de 384 dimensiones (e5-small, normalizado) |
| `metadata.dependencia` | Dependencia municipal responsable |
| `metadata.categoria` | Categoría para filtros (una de las 10 oficiales de `scripts/config_pipeline.py`) |
| `metadata.descripcion` | Descripción enriquecida |
| `metadata.fecha_actualizacion` | `YYYY-MM-DD` |
| `metadata.hash_sha256` | Hash del CSV, para detectar duplicados (en todos los datasets) |
| `metadata.archivo_original` | Nombre del CSV de origen (solo en datasets del catálogo cargados con `migrate_chroma.py`) |

**Metadato de la colección:** `modelo_embeddings` = modelo con que se generaron los vectores (lo comprueba la app al arrancar).

### 7.2 Base relacional (SQLAlchemy + Alembic)

`app/db_core/connection.py` elige el motor según `DATABASE_URL`:

- **Producción:** PostgreSQL (por ejemplo, Azure Database for PostgreSQL), usando `psycopg2-binary`.
- **Desarrollo:** SQLite en `data/usuarios.db`.

```mermaid
erDiagram
    usuarios {
        int id PK
        string username UK
        string password_hash "Argon2 (o bcrypt antiguo)"
        string rol "admin | editor"
    }
    mensajes_contacto {
        int id PK
        string nombre
        string email
        text mensaje
        datetime fecha_envio "UTC"
    }
    bitacora_auditoria {
        int id PK
        string usuario
        string accion
        string detalles
        datetime fecha_hora "UTC"
    }
    descargas_datasets {
        string id_dataset PK "ID en ChromaDB"
        int total_descargas
    }
```

El esquema se versiona con **Alembic** (`alembic/versions/`). La app aplica las migraciones pendientes al arrancar. Con una sola réplica es seguro; con varias, conviene ejecutarlas como un paso previo del despliegue.

---

## 8. Referencia de la API

Leyenda de acceso: 🌐 público · 🔑 sesión válida (admin o editor) · 🛡️ solo administrador

### Búsqueda y catálogo

| Método | Ruta | Acceso | Límite | Descripción |
|---|---|---|---|---|
| GET | `/api/buscar?prompt=...` | 🌐 | 15/min por IP | Búsqueda semántica. `prompt` de 2 a 300 caracteres (`422` si no) |
| GET | `/api/catalogos` | 🌐 | — | Catálogo completo con contadores de descargas |
| GET | `/api/descargar/{id}?formato=csv\|json\|xml\|geojson` | 🌐 | — | Descarga el dataset e incrementa su contador. `id` debe ser un UUID y `formato` uno de los cuatro (`422` si no, sin contar la descarga) |

**Ejemplo de respuesta de `/api/buscar`:**

```json
{
  "busqueda": "dónde tiro mis llantas viejas",
  "resultados": [
    {
      "id": "3f2c...-uuid",
      "dataset_recomendado": "Centros de Acopio de Neumáticos",
      "descripcion": "Ubicación de centros de acopio de llantas...",
      "dependencia": "Dirección General de Medio Ambiente",
      "categoria": "Medio Ambiente",
      "fecha_actualizacion": "2026-10-22",
      "distancia": 0.1612,
      "descargas": 14
    }
  ]
}
```

`fecha_actualizacion` es `null` si el dataset no tiene fecha; el frontend muestra "Sin fecha".

### Autenticación

| Método | Ruta | Acceso | Límite | Descripción |
|---|---|---|---|---|
| POST | `/api/login` | 🌐 | 5/min por IP | Body `{"usuario", "password"}` (máx. 50 y 128 caracteres). Si las credenciales son válidas, emite una cookie `access_token` |
| POST | `/api/logout` | 🌐 | — | Elimina la cookie de sesión |
| GET | `/api/auth/me` | 🔑 | — | Devuelve `{username, rol}` del usuario en sesión |

### Administración de datasets

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/admin/datasets` | 🔑 | Lista el catálogo para el panel |
| POST | `/api/admin/subir` | 🔑 | Publica un dataset (`multipart/form-data`: `titulo` ≤ 200, `descripcion` ≤ 2000, `dependencia` ≤ 200, `categoria` ≤ 100, `archivo`) |
| PUT | `/api/admin/datasets/{id}` | 🔑 | Actualiza los metadatos y regenera el embedding |
| DELETE | `/api/admin/datasets/{id}` | 🛡️ | Borra el vector, el CSV y el contador de descargas |

### Auditoría

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/admin/bitacora` | 🛡️ | Últimos 15 eventos |
| GET | `/api/admin/bitacora/exportar` | 🛡️ | Historial completo en CSV (`bitacora_auditoria_YYYYMMDD_HHMM.csv`) |

### Usuarios

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/api/admin/usuarios` | 🛡️ | Lista los funcionarios |
| POST | `/api/admin/usuarios` | 🛡️ | Crea un funcionario: `username` (3–50), `password` (6–72), `rol` (`admin`\|`editor`) |
| DELETE | `/api/admin/usuarios/{id}` | 🛡️ | Elimina un funcionario (no se puede eliminar la propia cuenta) |

### Contacto

| Método | Ruta | Acceso | Límite | Descripción |
|---|---|---|---|---|
| POST | `/api/contacto` | 🌐 | 5/min por IP | `nombre` (3–100), `email` válido, `mensaje` (10–2000) |
| GET | `/api/admin/mensajes` | 🔑 | — | Lista los mensajes del buzón |
| DELETE | `/api/admin/mensajes/{id}` | 🛡️ | — | Elimina un mensaje |

### Monitoreo

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/status` | Comprueba que el servidor responde |
| GET | `/api/health/live` | *Liveness probe* |
| GET | `/api/health/ready` | *Readiness probe*: verifica el warm-up, la compatibilidad del índice vectorial con el modelo y la conexión a la BD. Devuelve `503` si algo falla |

### Páginas y estáticos

`pages.py` sirve las páginas HTML: `/`, `/explorar_datos.html`, `/gobierno_abierto.html`, `/apis.html`, `/guia_usuario.html`, `/contacto.html`, `/preguntas_frecuentes.html`, `/aviso_privacidad.html`, `/terminos_uso.html`, `/politicas_datos_abiertos.html`, `/login.html` y `/admin.html`. FastAPI genera además `/docs` (Swagger) y `/redoc`.

Montajes estáticos: `/css`, `/js` y `/assets` (desde `frontend/`). Los CSV **no** se sirven como estáticos: todas las descargas pasan por `/api/descargar`, que las contabiliza.

---

## 9. Autenticación y control de acceso

### Flujo

```mermaid
sequenceDiagram
    participant N as Navegador
    participant API as FastAPI
    participant DB as BD relacional
    N->>API: POST /api/login {usuario, password}
    API->>DB: Buscar usuario
    API->>API: verificar_password (Argon2; hash ficticio si no existe)
    API->>DB: (si el hash era bcrypt) guardar hash Argon2 nuevo
    API-->>N: Set-Cookie: access_token=JWT (HttpOnly, SameSite=Lax, 30 min)
    N->>API: GET /api/admin/... (cookie automática)
    API->>API: jwt.decode → sub
    API->>DB: (si requiere_admin) verificar rol == admin
    API-->>N: 200 / 401 / 403
```

- **Token:** JWT HS256 (PyJWT) con los claims `sub` (usuario), `rol` y `exp`. Expira a los **30 minutos**. Un token vencido, alterado o firmado con otra clave responde `401`.
- **Transporte:** cookie `HttpOnly`, lo que impide que JavaScript lea el token y reduce el riesgo de XSS. Tiene `SameSite=Lax` y lleva `Secure` cuando `ENVIRONMENT=production`.
- **Contraseñas** (`app/security.py`):
  - Las nuevas se cifran con **Argon2**.
  - Los hashes **bcrypt** creados antes con passlib se siguen aceptando y se **migran a Argon2** la primera vez que el usuario inicia sesión. Para verificarlos se trunca la contraseña a 72 bytes, igual que hacía bcrypt 4, así que las contraseñas largas con acentos siguen funcionando.
  - Si el usuario no existe, se verifica contra un **hash ficticio** para que el tiempo de respuesta sea el mismo y no se pueda averiguar qué usuarios existen.
- **Dependencias de FastAPI:**
  - `verificar_token`: exige una sesión válida y devuelve el nombre de usuario.
  - `requiere_admin`: además, consulta el rol **en la base de datos** (no en el token), así que un cambio de rol surte efecto de inmediato.

### Roles

| Acción | `editor` | `admin` |
|---|:---:|:---:|
| Ver el catálogo y los mensajes del panel | ✅ | ✅ |
| Publicar y editar datasets | ✅ | ✅ |
| Eliminar datasets | ❌ | ✅ |
| Eliminar mensajes | ❌ | ✅ |
| Ver y exportar la bitácora | ❌ | ✅ |
| Gestionar funcionarios | ❌ | ✅ |

---

## 10. Gestión de datasets

### Publicación (`POST /api/admin/subir`)

Las validaciones se aplican en este orden:

1. Los campos de texto respetan sus longitudes máximas (`422` si no).
2. La extensión debe ser `.csv`.
3. El tamaño máximo es **25 MB** (`413` si se supera).
4. El contenido debe ser un **CSV legible**: se rechazan los archivos binarios renombrados (con bytes nulos) y los que pandas no puede leer, ni en `utf-8` ni en `latin-1`. No se confía en el `content-type`, que lo manda el navegador y se puede falsificar.
5. Se calcula el **SHA-256** del contenido y se busca en ChromaDB con un filtro (`where={"hash_sha256": ...}`). Si ya existe, se responde `409 Conflict`.

Después:

6. Se genera el embedding **antes** de escribir nada.
7. Se guarda el archivo en `data/raw/{uuid}.csv` y se inserta en ChromaDB. Si ChromaDB falla, el CSV se borra (no quedan archivos huérfanos) y se responde `500` con un mensaje genérico.
8. El evento se registra en la bitácora (tabla y `logs/auditoria.log`).

### Edición (`PUT /api/admin/datasets/{id}`)

Reemplaza el título, la descripción, la dependencia y la categoría, **regenera el embedding** y actualiza la fecha. Parte de los metadatos existentes, así que **conserva `hash_sha256` y `archivo_original`**. Sin `archivo_original`, `migrate_chroma.py` no reconocería el dataset y lo duplicaría.

### Eliminación (`DELETE /api/admin/datasets/{id}`)

Borra en cascada lógica:

1. El registro en ChromaDB.
2. El archivo `data/raw/{id}.csv`.
3. El contador en `descargas_datasets`.

También registra el evento en la bitácora.

### Descarga y conversión de formatos

| Formato | Implementación |
|---|---|
| `csv` | Se entrega el archivo original (`FileResponse`) |
| `json` | `DataFrame.to_json(orient="records")` |
| `xml` | `DataFrame.to_xml()`, con los nombres de columna saneados (`\W+` → `_`) |
| `geojson` | Un `Feature` por fila. Si existen las columnas `latitud`/`lat` y `longitud`/`lon` con valores numéricos, se genera una geometría `Point`; si no, `geometry: null` |

La lectura intenta primero con `utf-8` y, si falla, recurre a `latin-1`. Cada descarga válida incrementa el contador; un formato inválido se rechaza (`422`) antes de contar.

---

## 11. Frontend

FastAPI sirve el frontend como plantillas Jinja2, sin build ni frameworks pesados.

| Página | Script | Función |
|---|---|---|
| `index.html` | `index.js` | Portada con caja de búsqueda; redirige a la exploración |
| `explorar_datos.html` | `busqueda.js` | Búsqueda semántica, filtros por dependencia y categoría, ordenamiento, paginación, ficha de detalle (modal), descarga en varios formatos. Sincroniza los filtros con la URL |
| `login.html` | `login.js` | Inicio de sesión |
| `admin.html` | `admin.js` | Panel con pestañas: **Dashboard** (KPIs + Chart.js), **Subir**, **Gestionar catálogo**, **Buzón ciudadano**, **Funcionarios**. Oculta opciones según el rol (`/api/auth/me`) |
| `contacto.html` | `contacto.js` | Formulario del buzón ciudadano |
| Páginas informativas | — | Gobierno abierto, APIs, guía de usuario, FAQ, aviso de privacidad, términos de uso, políticas de datos abiertos |
| Todas | `accesibilidad.js` | Controles de accesibilidad |

**Buenas prácticas aplicadas:**

- Las funciones `escaparHTML` y `escaparAtributo` previenen XSS al pintar datos del servidor.
- **Todo el JavaScript vive en archivos `.js`**: no hay scripts inline ni atributos `onclick=`, lo que permite una CSP sin `'unsafe-inline'`.
- **Chart.js** se carga con versión fija (`chart.js@4.5.1`) y firma **SRI** (`integrity`): si el archivo del CDN cambia, el navegador se niega a ejecutarlo.
- Los inputs tienen los mismos `maxlength` que valida el backend.
- El CSS es Mobile-First, con Flexbox y Grid.
- La autorización se hace siempre en el servidor. El ocultamiento de opciones en el cliente es solo para la experiencia de usuario.

---

## 12. Scripts de ingesta y evaluación

Se pueden ejecutar desde cualquier carpeta: cada script se ubica en la raíz del proyecto. Las rutas y las categorías oficiales del pipeline están en `scripts/config_pipeline.py`.

### Pipeline de ingesta

```
data/entregados_municipio/*.csv
        │  analyze_csv.py (Gemini)
        ▼
data/clean/catalogo_maestro_procesado.csv   ← salida sin revisar
        │  revisión humana (intencional)
        ▼
data/clean/catalogo_maestro.csv             ← versión revisada
        │  migrate_chroma.py
        ▼
ChromaDB + data/raw/{id}.csv
```

La revisión humana es intencional: Gemini puede inventar una dependencia que suene oficial o describir mal un dataset.

### 12.1 `scripts/analyze_csv.py` — metadatos con IA

1. Lee cada CSV de `data/entregados_municipio/` que todavía no esté en el catálogo.
2. Envía una muestra de **5 filas** a Gemini (`GEMINI_MODEL`, por defecto `gemini-3.6-flash`).
3. Usa **salida estructurada**: un esquema Pydantic con `titulo`, `descripcion`, `dependencia` y `categoria`. `categoria` es un `Enum` con las 10 categorías oficiales, así que Gemini no puede inventar otra.
4. Ante errores temporales (429, 5xx o fallas de red) reintenta con **backoff exponencial** (2, 4, 8, 16 s). Un error de la solicitud (4xx) no se reintenta.
5. Guarda el catálogo después de cada archivo, así que si se interrumpe no se pierde lo ya procesado.

```bash
python scripts/analyze_csv.py                   # Solo procesa los CSV nuevos
python scripts/analyze_csv.py --forzar          # Vuelve a procesar todos
python scripts/analyze_csv.py --solo-columnas   # Privacidad: envía solo los encabezados, sin filas
```

> **Privacidad:** las filas de muestra se envían a la API de Google. Para archivos con datos personales, usa `--solo-columnas`.

### 12.2 `scripts/migrate_chroma.py` — carga idempotente

1. Lee `data/clean/catalogo_maestro.csv` (la versión revisada).
2. **Reutiliza el ID** de los datasets que ya están indexados (los busca por `archivo_original`), así que conservan su CSV en `data/raw/` y su contador de descargas. Los nuevos reciben un `uuid5` determinista.
3. Calcula `hash_sha256`, para que el panel detecte duplicados.
4. Recalcula los embeddings **de todos los datasets**, incluidos los subidos desde el panel, en lote, y los guarda con `upsert`.
5. Registra el modelo en el metadato `modelo_embeddings` de la colección.

```bash
python scripts/migrate_chroma.py --simular  # Muestra qué cambiaría
python scripts/migrate_chroma.py
```

Se puede ejecutar las veces que haga falta: no duplica datasets. Es el paso obligatorio después de **cambiar de modelo de embeddings**.

### 12.3 `scripts/evaluate_model.py` — calidad del buscador

Evalúa directamente contra ChromaDB, sin pasar por la API (así no le afectan el rate limit ni el umbral):

- **Recall@1, @5 y @10** y **MRR@10** sobre las 100 consultas de `eval/ground_truth.json`. El objetivo de la planeación es **Recall@5 ≥ 85 %**.
- **Recall@5 visible:** el dataset correcto en el Top-5 **y** dentro del umbral de la API, que es lo que realmente ve la ciudadanía.
- **Rechazo de consultas ajenas:** porcentaje de las 30 consultas de `eval/consultas_fuera_de_tema.json` que el umbral filtra.

```bash
python scripts/evaluate_model.py
python scripts/evaluate_model.py --calibrar --salida eval/resultados/e5_small.json
```

Si ChromaDB se indexó con otro modelo, el script se detiene y pide re-indexar.

**Resultados actuales (e5-small, umbral 0.19):** Recall@5 95 %, Recall@5 visible 89 %, rechazo de consultas ajenas 83 %.

### 12.4 `scripts/comparar_modelos.py` — comparación de modelos

Codifica en memoria los datasets indexados y las consultas con varios modelos (MiniLM, mpnet, e5-small, e5-base), **sin modificar ChromaDB**, y reporta las métricas y las distancias para calibrar el umbral.

```bash
python scripts/comparar_modelos.py
python scripts/comparar_modelos.py minilm e5-small --salida eval/resultados/comparacion.json
```

---

## 13. Seguridad

| Control | Implementación |
|---|---|
| Contraseñas | **Argon2** (pwdlib). Los hashes bcrypt antiguos se migran al iniciar sesión |
| Enumeración de usuarios | Verificación contra un hash ficticio cuando el usuario no existe, para igualar los tiempos de respuesta |
| Sesión | JWT (PyJWT) en una cookie `HttpOnly` y `SameSite=Lax`, `Secure` en producción, expiración de 30 min |
| Autorización | RBAC en el servidor; el rol se verifica contra la BD |
| Fuerza bruta / abuso | SlowAPI: login 5/min, contacto 5/min, búsqueda 15/min por IP. La IP se toma del **último** valor de `X-Forwarded-For` (el que agrega el proxy más cercano), no del primero, que el cliente podría inventar si algún proxy conserva la cabecera (`app/limiter.py`). El ingress de Azure reemplaza la cabecera con la IP real |
| Validación de entradas | Longitudes máximas en búsqueda, login, formularios y metadatos; IDs como `UUID`; formatos de descarga como `Literal` |
| Cabeceras HTTP | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Referrer-Policy`, `Content-Security-Policy` |
| CSP | Portal: `script-src` sin `'unsafe-inline'` y limitado a `'self'` y a la versión fija de Chart.js. `/docs` y `/redoc` tienen una CSP propia, porque FastAPI las genera con un script inline y recursos de CDN |
| Dependencias del frontend | Chart.js con versión fija y SRI |
| CORS | Lista blanca configurable (`ALLOWED_ORIGINS`) |
| Subida de archivos | Validación de extensión, tamaño y contenido (CSV legible, no binario); el archivo se renombra a un UUID (evita *path traversal*); detección de duplicados por SHA-256 |
| Errores | Los `500` devuelven un mensaje genérico; el detalle va al log con `logger.exception` |
| Inyección SQL | Consultas mediante el ORM de SQLAlchemy |
| XSS | Escapado en el frontend y CSP restrictiva |
| Secretos | `.env` excluido de git y de la imagen Docker |
| Imagen Docker | `.dockerignore` excluye `usuarios.db` (hashes de contraseñas), los CSV originales, `docs/`, `eval/` y `logs/` |
| Auditoría | Registro dual: tabla `bitacora_auditoria` y `logs/auditoria.log` |

---

## 14. Monitoreo y logging

- **Logging:** nivel `INFO` por defecto (`LOG_LEVEL`), que se envía a consola y a `logs/auditoria.log`. Con `LOG_LEVEL=DEBUG` se registran además el prompt y las distancias del top 10 de cada búsqueda, algo útil para depurar, pero que no conviene en producción.
- **Health checks** para orquestadores (Docker, Kubernetes, Azure Container Apps):
  - Liveness: `GET /api/health/live`
  - Readiness: `GET /api/health/ready` (devuelve `503` hasta que termina el warm-up, si el índice vectorial se creó con otro modelo o si la BD no responde)

---

## 15. Despliegue con Docker

### Imagen (`Dockerfile`)

- Base `python:3.12-slim`, con las dependencias de sistema para compilar LXML.
- **Descarga el modelo `intfloat/multilingual-e5-small` durante el build**, para que el contenedor arranque sin depender de Hugging Face.
- Copia `data/chroma_db` y `data/raw` desde la máquina donde se construye: **sin volumen** (como en Azure Container Apps), esos son los datasets que sirve la app. `data/` no está en git, así que **hay que re-indexar con `migrate_chroma.py` antes de construir** si cambió el modelo o el catálogo. Si se olvida, el *readiness* responde `503` en lugar de servir búsquedas incorrectas.
- Uvicorn arranca con `--proxy-headers --forwarded-allow-ips=*` para respetar `X-Forwarded-Proto`, porque Azure termina el HTTPS. Con `*`, Uvicorn toma la **primera** IP de `X-Forwarded-For`, que detrás de un proxy que conserve la cabecera podría falsificar el cliente; por eso el rate limit no usa esa IP, sino la última (ver [13. Seguridad](#13-seguridad)). En Azure la cabecera trae una sola IP, la real.

### Compose (`docker-compose.yml`)

```bash
docker compose up -d --build
```

Volúmenes persistentes:

| Host | Contenedor | Contenido |
|---|---|---|
| `./data/chroma_db` | `/app/data/chroma_db` | Índice vectorial |
| `./data/raw` | `/app/data/raw` | Archivos CSV publicados |
| `./data/usuarios.db` | `/app/data/usuarios.db` | Base SQLite |
| `./logs` | `/app/logs` | Logs de auditoría |

> Si `./data/usuarios.db` no existe en el host antes del primer `up`, Docker crea un **directorio** con ese nombre y SQLite falla. Crea el archivo antes con `touch data/usuarios.db`, o usa `DATABASE_URL` con PostgreSQL.

### Azure Container Apps

| Recurso | Valor |
|---|---|
| Container App | `app-portal-datos` (grupo `rg-portal-datos`, región Mexico Central) |
| URL | https://app-portal-datos.niceground-95b8d2a4.mexicocentral.azurecontainerapps.io |
| Registro | `acrportaldatos6462.azurecr.io/portal-datos-leon` (ACR Basic) |
| Versión desplegada | **`v6`** (desde 2026-10-22). `v5`, la versión anterior a la revisión (MiniLM), se conserva en el registro para volver atrás |
| Recursos | 1 vCPU, 2 GiB |
| Escala | Mínimo 0, máximo **1** réplica: se apaga cuando nadie lo usa (la primera visita espera la carga del modelo) y con una sola réplica la SQLite y el rate limit son consistentes |
| Base relacional | SQLite dentro del contenedor (sin `DATABASE_URL`): los usuarios se recrean desde `ADMIN_USER`/`ADMIN_PASSWORD` y los datos del panel se pierden al reiniciar (aceptado para la demo) |
| Variables | `ENVIRONMENT=production`, `ALLOWED_ORIGINS`; `SECRET_KEY` y `ADMIN_PASSWORD` como **secretos** del Container App (`secretRef`) |
| Probes | **Startup** y **readiness** en `/api/health/ready` (el tráfico solo llega cuando el modelo cargó y el índice es compatible); **liveness** en `/api/health/live` |

Para publicar una versión nueva:

```bash
python scripts/migrate_chroma.py --simular   # Debe mostrar 0 cambios: la imagen copia esta Chroma
docker build -t acrportaldatos6462.azurecr.io/portal-datos-leon:vN .
az acr login -n acrportaldatos6462
docker push acrportaldatos6462.azurecr.io/portal-datos-leon:vN
az containerapp update -n app-portal-datos -g rg-portal-datos --image acrportaldatos6462.azurecr.io/portal-datos-leon:vN
```

Para volver a la versión anterior, el mismo `az containerapp update` con la etiqueta previa (`:v5`). `v5` trae su propia Chroma indexada con MiniLM, así que es coherente por sí sola.

`az containerapp update --image` solo cambia la imagen: las réplicas, los probes, las variables y los secretos se conservan.

### Despliegue de `v6` (2026-10-22)

Verificado contra la URL pública después de desplegar:

- `/api/health/ready` responde `200`; el catálogo tiene los 75 datasets.
- Búsquedas con e5: "dónde tiro mis llantas viejas" → *Centros de Acopio de Neumáticos*; "se fundió el foco de la calle" → *Reportes de Fallas en Alumbrado Público*; "receta de pastel de chocolate" → sin resultados.
- Un login real devuelve la cookie con `HttpOnly; Secure; SameSite=lax`.
- Rate limit: de 16 intentos rápidos de login con IPs falsas en `X-Forwarded-For`, 7 recibieron `429`.
- Chromium (Playwright): las páginas públicas, la búsqueda, `/docs` y `/redoc` cargan sin errores de consola ni de CSP.
- Las sesiones abiertas siguen siendo válidas: los secretos conservan los valores que tenían como variables.

**No medido:** el tiempo de arranque en frío (escala desde 0). El *startup probe* le da hasta ~4 minutos para cargar el modelo.

### Checklist de producción

Marcado = aplicado en el despliegue actual de Azure.

- [x] Definir `ENVIRONMENT=production` (activa la cookie `Secure`).
- [x] Usar una `SECRET_KEY` larga y aleatoria.
- [x] Ajustar `ALLOWED_ORIGINS` al dominio real.
- [ ] Configurar `DATABASE_URL` hacia PostgreSQL. *No aplica a la demo: se decidió seguir con SQLite efímera.*
- [x] Servir detrás de HTTPS (la cabecera HSTS ya está activa).
- [x] Re-indexar con `migrate_chroma.py` antes de construir la imagen si cambió el modelo o el catálogo.
- [ ] Respaldar periódicamente `data/chroma_db`, `data/raw` y `data/clean`. *Importante: `data/` no está en git y la imagen copia la Chroma local, así que la copia de tu máquina es la única. Hay un respaldo de la versión MiniLM en `~/.cache/respaldo_chroma_minilm_2026-10-22`.*
- [x] Mantener `LOG_LEVEL` en `INFO` (el valor por defecto).
- [x] Guardar `SECRET_KEY` y `ADMIN_PASSWORD` como secretos, no como variables en texto plano.
- [x] Configurar los probes de startup, readiness y liveness.

---

## 16. Historial de problemas resueltos

La revisión de código del 2026-10-07 (`docs/pendientes.md`) detectó varios fallos. Esta tabla resume cómo se resolvió cada uno.

| Problema | Causa | Solución | PR |
|---|---|---|---|
| **La evaluación Top-5 no medía nada real** | Comparaba contra `archivo_original`, un campo que `/api/buscar` no devuelve; con la cadena vacía, `"" in texto` siempre es `True`, así que cualquier consulta con resultados contaba como acierto. Además, el rate limit de 15/min respondía `429` a la mayoría de las 100 consultas | `evaluate_model.py` consulta ChromaDB directamente y compara el archivo exacto. La línea base real resultó ser **78 %** | #2 |
| El modelo no alcanzaba la meta del 85 % | MiniLM llegaba a 78 % (y solo 65 % visible con el umbral de 0.60) | Cambio a `multilingual-e5-small` (95 %), umbral recalibrado a 0.19 | #7 |
| La subida de un CSV bloqueaba el servidor | `publicar_dataset` era `async def` con trabajo de CPU (embedding) | Endpoint `def`, que FastAPI ejecuta en un threadpool | #3 |
| Errores internos expuestos al cliente | `detail=f"... {str(e)}"` | Mensaje genérico + `logger.exception` | #3 |
| Logging fijo en `DEBUG` | `level=logging.DEBUG` | `LOG_LEVEL`, `INFO` por defecto | #3 |
| Entradas sin límites | `prompt`, IDs y metadatos sin validar | Longitudes máximas, `UUID`, `Literal` | #3, #8 |
| Dependencias de seguridad sin mantenimiento | `python-jose` y `passlib` (que obligaba a fijar `bcrypt==4.0.1`) | PyJWT y pwdlib con Argon2, con migración automática de los hashes bcrypt | #5 |
| Enumeración de usuarios por tiempo | Si el usuario no existía, no se calculaba ningún hash | Hash ficticio | #5 |
| La imagen Docker incluía `usuarios.db` | `.dockerignore` no excluía `data/` | Se excluyen `usuarios.db`, los CSV originales, `docs/`, `eval/` y `logs/` | #5 |
| Sin migraciones de esquema | `create_all` no modifica tablas existentes | Alembic, con registro automático de las bases anteriores | #6 |
| `migrate_chroma.py` duplicaba el catálogo | `uuid4` nuevo en cada ejecución y `add` en lugar de `upsert` | Reutiliza IDs, `uuid5` para los nuevos, `upsert`, `hash_sha256` | #6 |
| Los scripts de ingesta leían archivos distintos | `analyze_csv.py` escribía `..._procesado.csv` y `migrate_chroma.py` leía `catalogo_maestro.csv` | La diferencia es intencional (revisión humana): se documentó y las rutas se centralizaron en `config_pipeline.py` | #6 |
| La detección de duplicados no cubría la carga masiva | `migrate_chroma.py` no guardaba `hash_sha256` | Ahora lo guarda | #6 |
| Parseo frágil de la respuesta de Gemini | Limpieza de ```` ```json ```` con `replace` y categorías libres | Salida estructurada con Pydantic y `Enum` de categorías | #6 |
| Archivos huérfanos al fallar una subida | El CSV se escribía antes de generar el embedding | Embedding primero; si ChromaDB falla, se borra el CSV | #8 |
| Editar un dataset podía duplicarlo al re-indexar | La edición perdía `archivo_original` | La edición conserva los metadatos existentes | #8 |
| Las descargas por `/data/` no se contaban | `app.mount("/data", StaticFiles(...))` | Se quitó el montaje | #8 |
| Formato inválido sumaba al contador | Se incrementaba antes de validar el formato | `Literal` + validación previa | #8 |
| Fecha por defecto inventada | `meta.get("fecha_actualizacion", "2026-01-01")` | `null` y "Sin fecha" en el frontend | #8 |
| Detección de duplicados lenta | Cargaba toda la colección | Filtro `where={"hash_sha256": ...}` | #8 |
| `datetime.utcnow()` obsoleto | Python 3.12 | `ahora_utc()` | #8 |
| CSP con `'unsafe-inline'` en `script-src` | — | Se quitó (no hay JS inline); CSP propia para `/docs` y `/redoc` | #8, #9 |
| Chart.js sin versión fija | `cdn.jsdelivr.net/npm/chart.js` cargaba siempre la última versión | Versión 4.5.1 con SRI; CSP limitada a esa ruta | #10 |
| Rate limit dependiente del proxy | Con `--forwarded-allow-ips=*`, Uvicorn toma la primera IP de `X-Forwarded-For`, que el cliente puede escribir si un proxy conserva la cabecera. **En Azure no era explotable:** los logs muestran que el ingress reemplaza la cabecera con la IP real | Defensa adicional: el rate limit usa la última IP de la cabecera (`obtener_ip_cliente` en `app/limiter.py`) | #11 |
| Configuración de Azure incompleta | Sin probes, hasta 2 réplicas con SQLite y rate limit separados, secretos en texto plano y cookie sin `Secure` | Probes, máximo 1 réplica, secretos con `secretRef` y `ENVIRONMENT=production` | Despliegue `v6` |

El análisis detallado de la evaluación y del cambio de modelo está en `eval/experimentos/`.

---

## 17. Problemas conocidos y trabajo futuro

| # | Tema | Detalle |
|---|---|---|
| 1 | IP en los logs de acceso | Los logs de Uvicorn muestran la primera IP de `X-Forwarded-For`. En Azure es la real porque el ingress reemplaza la cabecera, pero detrás de otro proxy podría ser falsa. El rate limit ya no depende de ella |
| 2 | Rate limit por réplica | SlowAPI cuenta en memoria y se reinicia con cada arranque. Con el máximo de 1 réplica es suficiente; si se escala, usar `storage_uri="redis://..."` |
| 3 | Persistencia en Azure Container Apps | Sin volumen ni PostgreSQL, los datasets subidos desde el panel, los usuarios creados, la bitácora y `logs/auditoria.log` se pierden cada vez que el contenedor se apaga (también al escalar a 0). Es aceptable mientras el despliegue sea de demostración; la opción más directa sería un PostgreSQL con **pgvector** |
| 4 | Umbral fijo | Las distancias de los aciertos y de las consultas ajenas se traslapan: con 0.19 quedan 6 aciertos ocultos por muy poco y 5 consultas ajenas aceptadas. Un umbral relativo o un re-ranker podrían mejorarlo |
| 5 | Nombres propios locales | 5 consultas siguen fuera del Top-5, casi todas por nombres que un modelo general no conoce ("oruga", "Tota Carbajal", "Poliforum"). Candidatas para **fine-tuning** o **búsqueda híbrida** (BM25 + embeddings) |
| 6 | `analyze_csv.py` sin prueba real | La salida estructurada y los reintentos se probaron con un cliente simulado; falta una corrida contra la API de Gemini |
| 7 | Catálogo sin paginación en el servidor | `/api/catalogos` devuelve todo y la paginación se hace en el cliente. Es suficiente para unos cientos de datasets |
| 8 | Sin pruebas automatizadas | Las pruebas de cada fase se hicieron con `TestClient` y Playwright, pero no hay una suite de `pytest` en el repositorio |
| 9 | Configuración dispersa | `load_dotenv()` solo se llama en `auth.py` (y en `analyze_csv.py`). `main.py` lee `ADMIN_USER` porque importa `auth.py` antes del `lifespan`: funciona, pero depende del orden de los imports. Se puede centralizar con `pydantic-settings`, que ya está en `requirements.txt` |
| 10 | Tamaño de la imagen | ~3.8 GB, de los que ~1 GB son PyTorch y sus dependencias. Se podría reducir con ONNX Runtime (ya instalado por ChromaDB) y quitando `build-essential` del Dockerfile |
