# Revisión de código: Buscador Semántico de Datos Abiertos

**Repositorio:** `FMarin2401/buscador_semantico_datasets_gubernamental` (rama `master`, commit `b0bb396`, 2026-10-07)
**Alcance:** backend (`app/`), scripts (`scripts/`), `Dockerfile`, `docker-compose.yml`, `requirements.txt`. No se revisó el frontend ni la configuración real de Azure.

---

## Estado (actualizado 2026-10-22)

El resto del documento se conserva tal como se escribió en la revisión. Esta tabla indica qué se resolvió y dónde.

| Punto | Tema | Estado | PR |
|---|---|---|---|
| 2.1 | Evaluación no confiable | ✅ Resuelto (línea base real: 78 %; con e5-small: 95 %) | #2, #7 |
| 2.2 | Persistencia en Azure Container Apps | ⏳ Pendiente (Fase 6). Aceptado mientras el despliegue sea de demostración | — |
| 2.3 | `publicar_dataset` bloqueaba el event loop | ✅ Resuelto | #3 |
| 2.4 | Rate limiting: IP falsificable | ✅ Resuelto: el rate limit usa la última IP de `X-Forwarded-For` (la que agrega Azure) y el Container App queda con máximo 1 réplica | #11 |
| 2.5 | `python-jose` y `passlib` | ✅ Resuelto (PyJWT y pwdlib con Argon2) | #5 |
| 3.1 | Sin migraciones | ✅ Resuelto (Alembic) | #6 |
| 3.2 | `migrate_chroma.py` no idempotente | ✅ Resuelto | #6 |
| 3.3 | Robustez del pipeline con Gemini | ✅ Resuelto (salvo una prueba contra la API real) | #6 |
| 3.4 | Enumeración de usuarios por tiempo | ✅ Resuelto | #5 |
| 3.5 | Errores internos expuestos | ✅ Resuelto | #3 |
| 3.6 | Logging en `DEBUG` fijo | ✅ Resuelto (`LOG_LEVEL`) | #3 |
| 3.7 | Validación de entradas | ✅ Resuelto | #3, #8 |
| 3.8 | Consistencia archivo / ChromaDB | ✅ Resuelto | #8 |
| 4.1 – 4.7 | Limpieza y eficiencia | ✅ Resuelto | #8 |
| 4.8 | Umbral de distancia fijo | ✅ Resuelto (en `app/nlp_model.py`, calibrado a 0.19) | #7 |
| 4.9 | CSP con `'unsafe-inline'` | ✅ Resuelto (y CSP propia para `/docs` y `/redoc`) | #8, #9 |

**Encontrados durante la implementación:**
- La edición de un dataset perdía `archivo_original`, lo que habría duplicado el dataset al re-indexar. Resuelto en #8.
- La imagen Docker incluía `usuarios.db`. Resuelto en #5.
- Chart.js se cargaba sin versión fija. Resuelto en #10 con versión 4.5.1 y SRI.

El estado actualizado del proyecto está en `docs/Documentación_Técnica_Buscador.md` (secciones 16 y 17).

---

## Resumen

El proyecto tiene una base sólida: buena separación por módulos, seguridad pensada desde el inicio (JWT en cookie HttpOnly, bcrypt, RBAC, rate limiting, cabeceras HTTP), health checks y un conjunto de evaluación con 100 consultas reales. Lo más urgente:

1. **El script de evaluación reporta resultados que no son confiables** (sección 2.1).
2. **Los datos en Azure Container Apps pueden perderse** si no hay almacenamiento persistente (sección 2.2).
3. **El endpoint de subida bloquea el servidor** mientras genera el embedding (sección 2.3).

| Prioridad | Cantidad | Tipo |
|---|---|---|
| Alta | 5 | Errores que afectan resultados, datos o seguridad |
| Media | 8 | Buenas prácticas con impacto real a mediano plazo |
| Baja | 9 | Limpieza, eficiencia y consistencia |

---

## 1. Lo que está bien

### Arquitectura y organización
- **Separación clara de responsabilidades:** routers por dominio en `app/api/`, base relacional en `app/db_core/`, base vectorial en `db_chroma.py` y modelo en `nlp_model.py`.
- **SQLite en desarrollo y PostgreSQL en producción** con una sola variable (`DATABASE_URL`) en `connection.py`.
- **Variables de entorno para todo lo sensible:** `SECRET_KEY`, credenciales del admin inicial, `GEMINI_API_KEY` y `ALLOWED_ORIGINS`. No hay secretos en el código.
- **Comentarios y docstrings** que explican la intención del código.

### Búsqueda semántica
- **`"hnsw:space": "cosine"` configurado explícitamente.** Chroma usa L2 por defecto, y coseno es lo correcto para embeddings de Sentence Transformers.
- **Texto de indexación bien compuesto:** `"{titulo}. {descripcion} Dependencia: {dependencia}"` incluye las señales más útiles sin pasarse del límite de 128 tokens.
- **`/api/buscar` es `def` y no `async def`**, así que `encode()` corre en el threadpool sin bloquear el event loop.
- **Warm-up en `lifespan`:** el modelo y ChromaDB se cargan al arrancar, no en la primera petición.
- **Umbral de distancia** para no devolver resultados irrelevantes.

### Ingesta con Gemini
- **Expansión de documentos:** el prompt pide sinónimos y palabras coloquiales en la descripción, lo que acerca los metadatos a cómo busca la gente.
- **Muestra de solo 5 filas** por CSV: ahorra tokens sin perder el contexto de las columnas.
- **SDK oficial actual (`google-genai`).**

### Seguridad
- **JWT en cookie `HttpOnly`**, con `secure` en producción y `samesite="lax"`.
- **`algorithms=[ALGORITHM]` explícito** al decodificar, lo que evita ataques de confusión de algoritmo.
- **La app no arranca sin `SECRET_KEY`.**
- **`requiere_admin` vuelve a consultar el rol en la base** en lugar de confiar en el token: si se le quita el rol a alguien, aplica de inmediato.
- **RBAC razonable:** los editores suben y editan, y solo los administradores borran y gestionan usuarios.
- **Contraseñas con bcrypt**, y `max_length=72` en el esquema de usuarios, que respeta el límite de bcrypt.
- **Mismo mensaje de error** para usuario inexistente y contraseña incorrecta.
- **Rate limiting por endpoint** con límites coherentes: login 5/min, contacto 5/min, búsqueda 15/min.
- **Cabeceras de seguridad:** HSTS, CSP, `X-Frame-Options`, `X-Content-Type-Options` y `Referrer-Policy`.
- **CORS con orígenes desde variable de entorno**, no `*`.
- **Validación con Pydantic** (`EmailStr`, longitudes mínimas y máximas).
- **Admin inicial creado desde `.env`**, sin credenciales por defecto en el código.

### Gestión de datos
- **Detección de duplicados por hash SHA-256** al subir un CSV.
- **Límite de tamaño de archivo (25 MB)** y validación de extensión.
- **Bitácora de auditoría doble** (archivo de log y tabla), con exportación a CSV.
- **Al borrar un dataset se limpian también su CSV y su conteo de descargas.**
- **Exportación multiformato** (CSV, JSON, XML y GeoJSON con detección de coordenadas).

### Operación
- **Probes de liveness y readiness separadas**, con la readiness revisando el warm-up y la base de datos.
- **`--proxy-headers` en Uvicorn** para obtener la IP real detrás del ingress.
- **Volúmenes en `docker-compose.yml`** para persistir datos en local.

### Evaluación
- **Ground truth de 100 consultas coloquiales y realistas** ("Se fundió el foco de la calle..."), con un objetivo de Top-5 Accuracy del 85%. Es una práctica que muchos proyectos profesionales no tienen. Necesita una corrección (sección 2.1), pero la base es excelente.

---

## 2. Cosas a mejorar: prioridad alta

### 2.1 El script de evaluación da resultados no confiables
**Archivo:** `scripts/evaluate_model.py`

**Problema A: casi todo cuenta como acierto.** El script compara contra `res.get("archivo_original", "")`, pero `/api/buscar` **no devuelve** el campo `archivo_original`. Entonces `meta_archivo` siempre es `""`, y en Python `"" in "cualquier texto"` es `True`. Resultado: **cualquier consulta con al menos un resultado se marca como acierto**, sea cual sea el dataset devuelto.

**Problema B: el rate limit corta la evaluación.** `/api/buscar` permite 15 peticiones por minuto y el script manda 100 con 0.05 s de pausa. A partir de la petición 16 el servidor responde `429`: esas consultas no cuentan como acierto ni como fallo, pero sí entran en el denominador.

**Consecuencia:** el porcentaje que imprime no mide la calidad real del buscador.

**Propuesta:**
- Evaluar **directamente contra ChromaDB** (sin HTTP), usando `generar_embedding` y `coleccion.query`. Esto evita el rate limit y el umbral de distancia, y permite comparar modelos limpiamente.
- Comparar por `archivo_original` desde los metadatos de Chroma, verificando primero que el campo no esté vacío.
- Agregar **MRR** y **Recall@1/@5/@10** además de Top-5 Accuracy.
- Mover las consultas a un archivo `eval/ground_truth.json` para reutilizarlas en el fine-tuning.

### 2.2 Persistencia en Azure Container Apps
**Archivos:** `app/db_chroma.py`, `manipulate_datasets.py`, `main.py`

ChromaDB (`./data/chroma_db`), los CSV subidos (`data/raw/`) y el log de auditoría (`logs/auditoria.log`) se escriben en el **disco del contenedor**. Los volúmenes de `docker-compose.yml` solo existen en local. En Container Apps:
- **El disco es efímero:** al reiniciar o desplegar una nueva revisión se pierden los datasets subidos desde el panel y el log.
- **Con varias réplicas, cada una tiene su propia copia:** un dataset subido en una réplica no aparece en las demás.

**Propuesta (por verificar contra la configuración real de Azure):**
- Montar **Azure Files** para `data/` y fijar **máximo 1 réplica**, o
- Correr Chroma como servidor aparte (`chromadb.HttpClient`), o migrar a **PostgreSQL + pgvector** (ya hay Postgres en producción).
- Para los CSV, considerar **Azure Blob Storage**.
- Enviar los logs a la salida estándar (stdout) para que los recoja Azure Monitor / Log Analytics, en lugar de un archivo local.

### 2.3 `publicar_dataset` bloquea el event loop
**Archivo:** `app/api/manipulate_datasets.py`

El endpoint es `async def`, pero dentro hace trabajo síncrono y pesado: `generar_embedding()` (CPU), escritura del archivo, consultas a Chroma y a la base. Mientras corre, **el servidor completo deja de atender otras peticiones**, incluidas las búsquedas.

**Propuesta:** convertirlo a `def`. FastAPI maneja `UploadFile` en endpoints síncronos usando `archivo.file`. Otra opción es mantener `async def` y envolver el trabajo pesado con `await run_in_threadpool(...)`.

### 2.4 Rate limiting: IP falsificable y contadores por réplica
**Archivos:** `Dockerfile`, `app/limiter.py`

- `--forwarded-allow-ips=*` hace que Uvicorn confíe en `X-Forwarded-For` **venga de quien venga**. Dependiendo de cómo lo maneje el ingress, un atacante podría mandar un encabezado falso en cada intento y saltarse el límite de 5 logins por minuto.
- SlowAPI cuenta en memoria: con N réplicas, el límite real se multiplica por N, y se reinicia con cada reinicio del contenedor.

**Propuesta:**
- Restringir `--forwarded-allow-ips` a la IP o rango del ingress y probar mandando un `X-Forwarded-For` falso.
- Con 1 réplica, la memoria es suficiente. Con varias, usar `storage_uri="redis://..."`.

### 2.5 Dependencias de seguridad sin mantenimiento
**Archivos:** `requirements.txt`, `app/api/auth.py`, `app/api/users.py`, `app/main.py`

- **`python-jose`** ha tenido poco mantenimiento y vulnerabilidades reportadas. La documentación de FastAPI ahora usa **PyJWT**. Además, el README dice PyJWT pero el código usa jose.
- **`passlib`** no recibe actualizaciones desde 2020. Por eso `bcrypt` está fijado en `4.0.1`: versiones más nuevas lo rompen.

**Propuesta:**
- Migrar a `PyJWT` (`import jwt`, capturar `jwt.InvalidTokenError`).
- Migrar a `pwdlib` con Argon2 (o usar `bcrypt` directamente), re-hasheando contraseñas al iniciar sesión.
- Centralizar `pwd_context` en un solo módulo: hoy se crea en `auth.py` y en `main.py`.

---

## 3. Cosas a mejorar: prioridad media

### 3.1 Sin migraciones de base de datos
**Archivo:** `app/main.py`

`Base.metadata.create_all()` solo crea tablas que no existen. Si se agrega una columna a un modelo, **producción no se entera** y la app falla con `column does not exist`.

**Propuesta:** adoptar **Alembic**. Como producción ya tiene tablas, la primera vez se usa `alembic stamp head` para marcar el estado actual sin recrearlas. Ejecutar las migraciones como un paso del despliegue (un *job*), no al arrancar cada réplica.

### 3.2 `migrate_chroma.py` no es idempotente y no coincide con `analyze_csv.py`
**Archivos:** `scripts/migrate_chroma.py`, `scripts/analyze_csv.py`

- Genera un `uuid4()` nuevo en cada ejecución: **correrlo dos veces duplica todos los datasets** y vuelve a copiar los CSV.
- `analyze_csv.py` guarda `catalogo_maestro_procesado.csv`, pero `migrate_chroma.py` lee `catalogo_maestro.csv`.

**Propuesta:**
- ID determinista con `uuid5(NAMESPACE, archivo_original)` y `coleccion.upsert(...)` en lugar de `add(...)`.
- Rutas compartidas en un módulo de configuración. Si el paso manual de revisión es intencional, documentarlo en el README.
- Generar los embeddings en lote (`modelo.encode(lista, batch_size=32)`) en lugar de uno por uno.
- Guardar `hash_sha256` también aquí, para que la detección de duplicados del panel funcione con los datasets iniciales.

### 3.3 Robustez del pipeline con Gemini
**Archivo:** `scripts/analyze_csv.py`

- **Parseo frágil:** limpiar ```` ``` ```` con `replace` falla si el modelo agrega texto extra. Usar **salida estructurada** (`response_mime_type="application/json"` + `response_schema` con Pydantic) y `respuesta.parsed`.
- **Categorías libres:** definir `categoria` como `Enum` en el esquema para que solo use las categorías oficiales.
- **`time.sleep(10)` fijo:** reemplazar por reintentos con *exponential backoff* solo ante errores 429 o 5xx.
- **Modelo fijo en el código:** moverlo a una variable de entorno (`GEMINI_MODEL`).
- **SDK duplicado:** quitar `google-generativeai` (descontinuado) de `requirements.txt`; solo se usa `google-genai`.
- **Privacidad:** las 5 filas de muestra se envían a una API externa. Revisar o anonimizar los CSV con datos personales.
- **Revisión humana:** Gemini puede inventar una dependencia que suene oficial. Validar el CSV generado antes de migrarlo.

### 3.4 Enumeración de usuarios por tiempo de respuesta
**Archivo:** `app/api/auth.py`

Si el usuario no existe, no se ejecuta `verify()` y la respuesta llega mucho más rápido que cuando sí existe (bcrypt tarda cientos de milisegundos). Midiendo los tiempos se puede saber qué usuarios existen.

**Propuesta:** cuando el usuario no exista, verificar contra un hash falso precalculado para igualar los tiempos.

### 3.5 Errores internos expuestos al cliente
**Archivos:** `manipulate_datasets.py` (actualizar y eliminar), `main.py` (readiness)

`detail=f"... {str(e)}"` puede revelar rutas, versiones o detalles de la base de datos.

**Propuesta:** registrar el error completo con `logger.exception(...)` y devolver un mensaje genérico, con un ID de error si se quiere rastrear.

### 3.6 Logging en nivel DEBUG fijo
**Archivo:** `app/main.py`

`level=logging.DEBUG` en todos los ambientes registra cada consulta de los ciudadanos y genera mucho ruido en producción.

**Propuesta:** leer el nivel de una variable (`LOG_LEVEL`, `INFO` por defecto en producción). Si se quieren analizar las consultas, hacerlo de forma deliberada y anonimizada.

### 3.7 Validación de entradas
**Archivos:** `search.py`, `manipulate_datasets.py`

- `prompt` no tiene longitud máxima. Agregar `prompt: str = Query(..., min_length=2, max_length=300)`.
- `id_dataset` se usa para construir rutas de archivo (`data/raw/{id_dataset}.csv`). FastAPI no deja pasar `/` en parámetros de ruta, pero conviene declararlo como `UUID` para rechazar cualquier valor inesperado.
- `content_type` lo manda el cliente y se puede falsificar. Validar que `pandas` pueda leer el archivo antes de guardarlo.
- Los campos de texto del formulario de subida no tienen límites de longitud.

### 3.8 Consistencia entre archivo, ChromaDB y base relacional
**Archivo:** `manipulate_datasets.py`

Al subir, primero se escribe el CSV y después se genera el embedding y se guarda en Chroma. Si falla algo a la mitad, queda un **archivo huérfano** en `data/raw/`.

**Propuesta:** generar el embedding antes de escribir el archivo y, si falla algún paso posterior, borrar lo que ya se escribió.

---

## 4. Cosas a mejorar: prioridad baja

1. **Código duplicado en `search.py`:** `/api/catalogos` y `/api/buscar` arman el mismo diccionario de resultado. Extraer una función `formatear_dataset(...)` o un modelo Pydantic de respuesta (`response_model`), que además documenta la API en `/docs`.
2. **Fecha por defecto falsa:** `meta.get("fecha_actualizacion", "2026-01-01")` muestra una fecha inventada. Usar `None` y que el frontend muestre "Sin fecha".
3. **Conteos de descargas en cada búsqueda:** se carga toda la tabla `DescargasDatasetModel`. Filtrar solo los IDs devueltos: `.filter(DescargasDatasetModel.id_dataset.in_(ids))`.
4. **Detección de duplicados carga toda la colección:** usar `coleccion.get(where={"hash_sha256": hash_calculado})`.
5. **El conteo de descargas sube aunque el formato sea inválido:** validar `formato` antes de incrementar, idealmente con `Literal["csv", "json", "xml", "geojson"]`.
6. **`/data` sirve los CSV directamente:** `app.mount("/data", StaticFiles(...))` permite descargar sin pasar por `/api/descargar`, así que esas descargas no se cuentan. Quitar el mount si no se usa.
7. **`datetime.utcnow()` está descontinuado** (Python 3.12+). Usar `datetime.now(timezone.utc)`.
8. **Umbral de distancia fijo (`0.60`):** moverlo a configuración y calibrarlo con el conjunto de evaluación corregido.
9. **CSP con `'unsafe-inline'` en `script-src`:** reduce la protección contra XSS. Mover los scripts inline a archivos `.js` y quitarlo.

---

## 5. Plan sugerido

| Paso | Tarea | Por qué primero |
|---|---|---|
| 1 | Corregir `evaluate_model.py` (2.1) y medir la línea base real | Sin una medición confiable no se puede saber si un cambio mejora o empeora |
| 2 | Confirmar la configuración de Azure: réplicas y almacenamiento (2.2) | Riesgo de perder datos |
| 3 | `publicar_dataset` a `def` (2.3) | Cambio de una línea con impacto inmediato |
| 4 | Ajustar `--forwarded-allow-ips` (2.4) | Cambio pequeño de seguridad |
| 5 | PyJWT y pwdlib (2.5) | Quita dependencias sin mantenimiento |
| 6 | Alembic (3.1) | Prepara el proyecto para cambiar modelos sin riesgo |
| 7 | Scripts idempotentes y salida estructurada de Gemini (3.2, 3.3) | Base para regenerar el índice tras el fine-tuning |
| 8 | Resto de prioridad media y baja | Limpieza continua |

Los pasos 1 y 7 son, además, la base del proyecto de **fine-tuning del modelo de embeddings**: el ground truth corregido sirve como conjunto de evaluación, y los scripts idempotentes permiten re-indexar todo con el modelo nuevo.
