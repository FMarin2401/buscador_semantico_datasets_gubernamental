# Diseño de la API

**Sistema:** Buscador Semántico de Datasets Gubernamentales, Municipio de León
**Estilo:** REST sobre HTTP, cuerpos en JSON (UTF-8). Implementada con FastAPI (`api/app/`).
**URL base (docker compose):** `http://localhost:8080`. nginx reenvía `/api`, `/docs`, `/redoc` y `/openapi.json` al contenedor de la API, que no publica puerto.
**Documentación interactiva:** `http://localhost:8080/docs` (Swagger) y `/redoc`. La especificación completa, con esquemas y ejemplos, está en `openapi.json` (exportado de `/openapi.json`).

---

## 1. Recursos

| Recurso | Ruta base | Operaciones |
|---|---|---|
| Datasets (catálogo) | `/api/catalogos`, `/api/buscar`, `/api/admin/datasets`, `/api/admin/subir` | Crear, consultar, buscar, editar, eliminar |
| Archivos de un dataset | `/api/descargar/{id}`, `/api/datasets/{id}/vista-previa` | Descargar (CSV, JSON, XML, GeoJSON), vista previa |
| Reportes de un dataset (SC-001) | `/api/datasets/{id}/reportes`, `/api/admin/reportes` | Crear, consultar, cambiar estado, eliminar |
| Mensajes del buzón | `/api/contacto`, `/api/admin/mensajes` | Crear, consultar, eliminar |
| Funcionarios | `/api/admin/usuarios` | Crear, consultar, eliminar |
| Sesión | `/api/login`, `/api/logout`, `/api/auth/me` | Iniciar, cerrar, consultar |
| Bitácora | `/api/admin/bitacora` | Consultar, exportar CSV |
| Salud del servicio | `/api/status`, `/api/health/*` | Consultar |

Convención: las rutas bajo `/api/admin/` son del panel y requieren sesión; el resto son públicas.

## 2. Tabla de endpoints

Acceso: 🌐 público · 🔑 sesión de administrador o editor · 🛡️ solo administrador.

### Búsqueda y catálogo

| Verbo | Ruta | Acceso | Descripción | Respuestas |
|---|---|---|---|---|
| GET | `/api/buscar?prompt=` | 🌐 | Búsqueda semántica en lenguaje natural (2 a 300 caracteres) | `200`, `422`, `429` |
| GET | `/api/catalogos` | 🌐 | Catálogo completo con descargas | `200` |
| GET | `/api/categorias` | 🌐 | Las 10 categorías oficiales | `200` |

### Datasets

| Verbo | Ruta | Acceso | Descripción | Respuestas |
|---|---|---|---|---|
| POST | `/api/admin/subir` | 🔑 | Publica un dataset (`multipart/form-data`: CSV ≤ 25 MB y metadatos) | `201`, `400`, `401`, `409`, `413`, `422`, `500` |
| GET | `/api/admin/datasets` | 🔑 | Catálogo con metadatos editables | `200`, `401` |
| PUT | `/api/admin/datasets/{id}` | 🔑 | Reemplaza los metadatos y recalcula el embedding | `200`, `401`, `404`, `422`, `500` |
| DELETE | `/api/admin/datasets/{id}` | 🛡️ | Elimina el dataset, su archivo, su contador y sus reportes | `200`, `401`, `403`, `404`, `422`, `500` |
| GET | `/api/descargar/{id}?formato=` | 🌐 | Descarga en `csv`, `json`, `xml` o `geojson`; suma una descarga | `200`, `404`, `422` |
| GET | `/api/datasets/{id}/vista-previa` | 🌐 | Columnas y primeras 5 filas | `200`, `404`, `422`, `429` |

### Reportes de datasets (SC-001)

| Verbo | Ruta | Acceso | Descripción | Respuestas |
|---|---|---|---|---|
| POST | `/api/datasets/{id}/reportes` | 🌐 | Reporta un problema; nace en estado `abierto` | `201`, `404`, `422`, `429` |
| GET | `/api/admin/reportes?estado=` | 🔑 | Lista los reportes, opcionalmente por estado | `200`, `401`, `422` |
| GET | `/api/admin/reportes/resumen-datasets` | 🔑 | Descargas y reportes por dataset (vista `v_resumen_datasets`) | `200`, `401` |
| PATCH | `/api/admin/reportes/{id}` | 🔑 | Cambia el estado (solo avanza) | `200`, `401`, `404`, `409`, `422` |
| DELETE | `/api/admin/reportes/{id}` | 🛡️ | Elimina un reporte | `200`, `401`, `403`, `404`, `422` |

### Buzón ciudadano

| Verbo | Ruta | Acceso | Descripción | Respuestas |
|---|---|---|---|---|
| POST | `/api/contacto` | 🌐 | Envía un mensaje | `201`, `422`, `429` |
| GET | `/api/admin/mensajes` | 🔑 | Lista los mensajes | `200`, `401` |
| DELETE | `/api/admin/mensajes/{id}` | 🛡️ | Elimina un mensaje | `200`, `401`, `403`, `404`, `422` |

### Sesión y funcionarios

| Verbo | Ruta | Acceso | Descripción | Respuestas |
|---|---|---|---|---|
| POST | `/api/login` | 🌐 | Inicia sesión; crea la cookie con el JWT | `200`, `401`, `422`, `429` |
| POST | `/api/logout` | 🌐 | Cierra sesión; borra la cookie | `200` |
| GET | `/api/auth/me` | 🔑 | Usuario y rol de la sesión | `200`, `401`, `404` |
| GET | `/api/admin/usuarios` | 🛡️ | Lista los funcionarios (sin contraseñas) | `200`, `401`, `403` |
| POST | `/api/admin/usuarios` | 🛡️ | Da de alta un funcionario | `201`, `401`, `403`, `409`, `422` |
| DELETE | `/api/admin/usuarios/{id}` | 🛡️ | Da de baja un funcionario | `200`, `400`, `401`, `403`, `404`, `422` |

### Bitácora y monitoreo

| Verbo | Ruta | Acceso | Descripción | Respuestas |
|---|---|---|---|---|
| GET | `/api/admin/bitacora` | 🛡️ | Últimos 15 eventos | `200`, `401`, `403` |
| GET | `/api/admin/bitacora/exportar` | 🛡️ | Bitácora completa en CSV | `200`, `401`, `403` |
| GET | `/api/status` | 🌐 | El servidor responde | `200` |
| GET | `/api/health/live` | 🌐 | *Liveness probe* | `200` |
| GET | `/api/health/ready` | 🌐 | *Readiness probe*: modelo, índice y base de datos | `200`, `503` |

## 3. Códigos de respuesta

| Código | Significado en esta API | Ejemplo |
|---|---|---|
| `200 OK` | Consulta, edición o eliminación correcta | `PUT /api/admin/datasets/{id}` |
| `201 Created` | Se creó un recurso | `POST /api/datasets/{id}/reportes` → `{"id": 12, "estado": "abierto", ...}` |
| `400 Bad Request` | El archivo no es un CSV válido, o un administrador intenta borrar su propia cuenta | `{"detail": "El contenido del archivo no es un CSV válido."}` |
| `401 Unauthorized` | Sin sesión, sesión expirada o credenciales incorrectas | `{"detail": "No se encontró la sesión activa"}` |
| `403 Forbidden` | Hay sesión, pero el rol no alcanza (un editor intenta borrar) | `{"detail": "Acceso denegado: se requiere rol de administrador."}` |
| `404 Not Found` | El recurso no existe | `{"detail": "Dataset no encontrado."}` |
| `409 Conflict` | Se viola una regla de negocio: archivo duplicado, usuario repetido o transición de estado no permitida | `{"detail": "Un reporte resuelto no se puede reabrir ni modificar."}` |
| `413 Content Too Large` | El CSV supera 25 MB | `{"detail": "El archivo excede el tamaño máximo permitido de 25 MB."}` |
| `422 Unprocessable Content` | Los datos no cumplen el esquema: campo faltante, longitud, valor fuera de la lista, UUID inválido | `{"detail": [{"loc": ["body", "tipo"], "msg": "Input should be 'datos_incorrectos', ..."}]}` |
| `429 Too Many Requests` | Se superó el límite de peticiones por IP | `{"error": "Rate limit exceeded: 5 per 1 minute"}` |
| `500 Internal Server Error` | Falló una base de datos; el detalle queda solo en el log del servidor | `{"detail": "Error al guardar el dataset en la base vectorial."}` |
| `503 Service Unavailable` | La app aún no está lista (cargando el modelo) | `/api/health/ready` |

Los errores propios devuelven siempre `{"detail": "<mensaje>"}`, en texto que el frontend muestra tal cual.

## 4. Reglas de negocio aplicadas en la API

| Regla | Endpoint | Error al violarla |
|---|---|---|
| El mismo archivo (mismo SHA-256) no se publica dos veces | `POST /api/admin/subir` | `409` |
| Solo se aceptan las categorías oficiales | `POST /api/admin/subir`, `PUT /api/admin/datasets/{id}` | `422` |
| El archivo debe leerse como CSV, no basta con la extensión | `POST /api/admin/subir` | `400` |
| Un reporte solo avanza (`abierto → en_revision → resuelto`) y uno resuelto queda cerrado | `PATCH /api/admin/reportes/{id}` | `409` |
| Un reporte pertenece a un dataset que existe | `POST /api/datasets/{id}/reportes` | `404` |
| No hay dos funcionarios con el mismo usuario | `POST /api/admin/usuarios` | `409` |
| Un administrador no puede borrar su propia cuenta | `DELETE /api/admin/usuarios/{id}` | `400` |
| Solo un administrador borra y administra usuarios | Rutas 🛡️ | `403` |

Las pruebas de `api/tests/` verifican cada una de estas reglas (`docker compose exec api pytest`).

## 5. Seguridad

### Autenticación: JWT en cookie HttpOnly

1. `POST /api/login` valida usuario y contraseña. Las contraseñas se guardan con **Argon2** (`pwdlib`); cuando el usuario no existe se calcula igual un hash, para que el tiempo de respuesta no revele qué usuarios existen. El mensaje de error es el mismo en ambos casos.
2. Si son correctas, la API firma un **JWT** (HS256, con `SECRET_KEY`) que contiene el usuario, su rol y una expiración de **30 minutos**.
3. El token viaja en la cookie **`access_token`** con `HttpOnly` (JavaScript no puede leerla, lo que protege contra robo por XSS), `SameSite=Lax` (protege contra CSRF desde otros sitios) y `Secure` en producción (solo por HTTPS).
4. Cada endpoint protegido verifica la firma y la expiración (`verificar_token`). Las rutas 🛡️ vuelven a consultar el rol en la base (`requiere_admin`): si se le quita el rol a alguien, aplica de inmediato, aunque su token siga vigente.
5. En OpenAPI la cookie se declara como el esquema de seguridad `APIKeyCookie`, por eso los endpoints protegidos aparecen con candado en `/docs`.

Se eligió cookie HttpOnly en lugar de un encabezado `Authorization` con el token guardado en `localStorage`, porque así un script inyectado no puede robar la sesión.

### Validación de entradas

- **Pydantic** valida cada cuerpo y parámetro antes de ejecutar el endpoint: tipos, longitudes mínimas y máximas, correos (`EmailStr`), listas cerradas (`Literal`) y UUID en las rutas. Lo que no cumple se rechaza con `422`.
- Los valores acotados (`rol`, `categoria`, `tipo`, `estado`) también tienen **`CHECK`** en PostgreSQL.
- Archivos: extensión `.csv`, tamaño máximo de 25 MB (`413`), contenido que pandas pueda leer y sin bytes binarios (`400`).
- Los IDs de las rutas se declaran como `UUID`: así nunca se usa un valor arbitrario para construir rutas de archivo.
- Los errores internos no exponen detalles (rutas, versiones, SQL): el cliente recibe un mensaje genérico y el detalle va al log.

### CORS

- `CORSMiddleware` solo permite los orígenes de la variable **`ALLOWED_ORIGINS`** (en `.env.example`: `http://localhost:8080`), nunca `*`. Como la API envía credenciales (la cookie), un `*` además no estaría permitido por los navegadores.
- En docker compose el frontend y la API comparten origen (nginx los sirve juntos), así que el navegador ni siquiera necesita CORS para el portal; la lista restringe a cualquier otro sitio que intente llamar a la API con la sesión del usuario.

### Otras medidas

| Medida | Detalle |
|---|---|
| Límite de peticiones (SlowAPI) | Login 5/min, contacto 5/min, reportes 5/min, búsqueda 15/min, vista previa 30/min por IP (`429`). La IP se toma del último valor de `X-Forwarded-For`, el que agrega nginx, para que el cliente no pueda falsificarla |
| Cabeceras de seguridad | `Content-Security-Policy` sin `'unsafe-inline'` en el portal, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Referrer-Policy` |
| Red privada | PostgreSQL está en una red de Docker `internal`: sin puertos publicados y solo accesible desde la API. La API tampoco publica puerto; todo entra por nginx (puerto 8080) |
| Secretos | `SECRET_KEY`, credenciales y la contraseña de PostgreSQL vienen de `.env`, que no se versiona; el repositorio solo trae `.env.example` |
| Auditoría | Cada acción administrativa queda en `bitacora_auditoria` con el funcionario que la hizo |
