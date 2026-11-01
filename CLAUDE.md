# CLAUDE.md

Instrucciones permanentes para trabajar en este repositorio con Claude Code (o cualquier persona nueva en el proyecto).

## Resumen

Portal de Datos Abiertos del Municipio de León con **búsqueda semántica**: el ciudadano escribe en lenguaje coloquial ("dónde tiro mis llantas viejas") y el sistema encuentra el dataset por significado, no por palabras exactas. Incluye descarga en CSV/JSON/XML/GeoJSON, buzón ciudadano, reportes de problemas en datasets (SC-001) y un panel para que los funcionarios publiquen y administren el catálogo.

Proyecto del 2.º parcial de Ingeniería de Software (Ibero León). La rúbrica exige frontend, API y base de datos en **contenedores separados** que se levanten con `docker compose up --build`.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | HTML (plantillas Jinja2 renderizadas a estático), CSS Mobile-First, JavaScript sin frameworks, Chart.js; servido por **nginx** |
| API | Python 3.12, **FastAPI**, Pydantic, SQLAlchemy 2, Alembic, SlowAPI, PyJWT, pwdlib (Argon2), pandas |
| ML | `intfloat/multilingual-e5-small` (sentence-transformers, CPU) y **ChromaDB** embebida (distancia coseno) |
| Base de datos | **PostgreSQL 16** en docker compose; SQLite en Azure y en desarrollo sin Docker |
| Ingesta offline | Google Gemini (`google-genai`) genera los metadatos de los CSV del municipio |
| Infraestructura | Docker Compose (3 servicios); Azure Container Apps para la demo pública (un solo contenedor) |
| Pruebas | pytest + `TestClient` de FastAPI |

## Estructura

```
api/                    Backend (contenedor "api")
  app/main.py           App, lifespan (migraciones, admin inicial, sincronización, warm-up), CORS, CSP, health checks
  app/api/              Routers: search, manipulate_datasets, reportes (SC-001), auth, users, contact, pages, esquemas
  app/db_core/          connection, models (FK y CHECK), migraciones, sincronizacion (ChromaDB -> tabla datasets), auditoria
  app/nlp_model.py      Modelo, prefijos query:/passage:, umbral de distancia (0.19)
  app/db_chroma.py      Cliente y colección de ChromaDB
  alembic/versions/     0001 esquema inicial, 0002 integridad referencial y reportes
  scripts/              analyze_csv (Gemini), migrate_chroma (indexa db/seed), evaluate_model, comparar_modelos
  tests/                pytest (conftest con base temporal)
  eval/                 Ground truth de 100 consultas y resultados de evaluación
frontend/               Contenedor "frontend": *.html (Jinja2), css/, js/, render.py, nginx.conf
db/seed/                Datos de ejemplo: catalogo_maestro.csv + 75 CSV del municipio
db/objetos_bd.sql       Índice y vista de PostgreSQL con su justificación
docs/                   Documentación técnica, solicitudes_cambio.md, entrega/ (DDA, Diseño de API, diagramas)
docker-compose.yml      db + api + frontend; solo frontend publica puerto (8080)
Dockerfile.azure        Imagen de un solo contenedor (API + frontend + SQLite) para Azure
```

## Comandos frecuentes

```bash
cp .env.example .env                      # Primera vez
docker compose up --build                 # Levantar todo (http://localhost:8080, Swagger en /docs)
docker compose up --build -d frontend     # Reconstruir solo el frontend tras cambiar HTML/CSS/JS
docker compose logs -f api                # Logs de la API
docker compose exec api pytest            # Pruebas (base temporal, no toca los datos)
docker compose exec db psql -U portal -d portal_datos   # Consola de PostgreSQL
docker compose down -v                    # Borrar todo y volver a los datos de ejemplo

# Sin Docker (desde api/, con el venv de la raíz: source ../env/bin/activate)
uvicorn app.main:app --reload             # http://localhost:8000 con SQLite y el frontend
pytest
alembic revision --autogenerate -m "..."  # Nueva migración (revisarla a mano)
alembic check                             # Modelos y migraciones coinciden
python scripts/migrate_chroma.py --simular
```

## Convenciones

- **Idioma:** código, comentarios, mensajes de error, commits y documentación en **español**. Nombres en `snake_case` (Python) y `camelCase` (JS), descriptivos (`registrar_evento_auditoria`, `cargarReportesAdmin`).
- **Comentarios:** explican el *porqué* (una decisión, un riesgo evitado), no lo que el código ya dice. Mantener la densidad del archivo que se edita.
- **Endpoints:** cada uno lleva `summary`, `description`, `response_model` con ejemplo (`json_schema_extra`) y `responses` con sus errores, usando los helpers de `app/api/esquemas.py` (`error()`, `ERROR_401`, `ERROR_403`, `ERROR_429`). `tests/test_documentacion.py` falla si falta algo.
- **Errores:** `HTTPException` con `detail` en texto legible (el frontend lo muestra tal cual). Errores internos: `logger.exception(...)` y un mensaje genérico al cliente.
- **Endpoints que generan embeddings** son `def`, no `async def` (FastAPI los corre en un threadpool y no bloquean las búsquedas).
- **Valores acotados** (`rol`, `categoria`, `tipo`, `estado`): `Literal` en Pydantic **y** `CHECK` en la base. Las categorías oficiales viven solo en `app/catalogo.py`.
- **Bitácora:** toda acción administrativa llama a `registrar_evento_auditoria(db, usuario, accion, detalles)` antes del `db.commit()` del cambio.
- **Catálogo:** ChromaDB es el índice; la tabla `datasets` es su copia relacional. Cualquier alta, edición o baja actualiza las dos (ver `manipulate_datasets.py`).
- **Frontend:** sin JavaScript inline (la CSP lo bloquea); todo texto dinámico pasa por `escaparHTML`/`escaparAtributo`; estados de carga, vacío y error en cada tabla; botones `.btn-primary` (principal) y `.btn-outline`/`.btn-secondary` (secundarios).
- **Pruebas:** en `api/tests/`, con los fixtures `como_admin`, `como_editor`, `sin_sesion`, `sesion(rol)` y `dataset`. Cada regla de negocio nueva lleva su prueba negativa.
- **Commits y ramas:** una rama por cambio (`feat/...`, `fix/...`, `docs/...`), mensaje en imperativo ("Agregar...", "Corregir..."), PR a `master` con merge commit y la rama se borra después.

## Reglas de trabajo

1. **Nunca** versionar `.env`, `api/data/` (incluye `usuarios.db` con hashes), `api/logs/`, `env/` ni `venv/`. Los datos de ejemplo van en `db/seed/`.
2. **Cambios de esquema solo con Alembic.** En las migraciones, las listas de valores se escriben a mano (no se importan de `app/`). Después de migrar, `alembic check` debe decir "No new upgrade operations detected". En SQLite, una migración que modifique una tabla usada por `v_resumen_datasets` debe borrar y recrear la vista.
3. **Índice o vista nuevos** se documentan también en `db/objetos_bd.sql` con su justificación.
4. **Cabeceras de seguridad:** la CSP de las páginas está en `api/app/main.py` y duplicada en `frontend/nginx.conf` (dentro de `location /`, nunca a nivel `server`, o `/docs` queda en blanco). Si cambia una, cambiar la otra.
5. **Antes de dar algo por terminado:** pruebas en verde dentro del contenedor, revisar en el navegador las pantallas afectadas (sin errores de consola), y para cambios de infraestructura, levantar desde un clon limpio con `cp .env.example .env && docker compose up --build`.
6. **Azure se queda con SQLite y un solo contenedor** (`Dockerfile.azure`, réplicas 0 a 1): es una demo de cuenta estudiantil sin costo. No proponer PostgreSQL administrado ni almacenamiento pagado en Azure.
7. **Toda solicitud de cambio** se registra en `docs/solicitudes_cambio.md` (folio, descripción, reglas, impacto por capa, estado) y se agrega a la sección siguiente de este archivo.
8. Actualizar `README.md` y `docs/Documentación_Técnica_Buscador.md` en el mismo PR cuando cambie el comportamiento, la estructura o los comandos.

## Solicitudes de cambio

| Folio | Cambio | Estado | Dónde vive |
|---|---|---|---|
| SC-001 | Reportar problemas en un dataset: el ciudadano reporta desde la ficha; el panel atiende con estados `abierto → en_revision → resuelto` (no retrocede; reabrir un resuelto da `409`) | Implementada | BD: tablas `reportes_dataset` y `datasets`, índice `ix_reportes_estado_fecha`, vista `v_resumen_datasets` (migración `0002`). API: `app/api/reportes.py`. Front: ficha en `explorar_datos.html`/`js/busqueda.js` y pestaña «Reportes» en `admin.html`/`js/admin.js`. Pruebas: `tests/test_reportes.py` |

Al implementar una SC nueva: rama propia, migración si toca la base, endpoints documentados, pruebas negativas de sus reglas, pantallas con estados vacío y de error, y registro aquí y en `docs/solicitudes_cambio.md`.
