# Diccionario de Datos (DDA)

**Sistema:** Buscador Semántico de Datasets Gubernamentales, Municipio de León
**Motor:** PostgreSQL 16 (contenedor `db`). El esquema lo crean las migraciones de Alembic `0001` y `0002` (`api/alembic/versions/`).
**Diagrama:** `DER.drawio` / `DER.png`. **Índice y vista:** `objetos_bd.sql`.

Convenciones de las tablas:

- **Nulo:** `NO` = obligatorio, `SÍ` = opcional.
- **Llave:** `PK` llave primaria, `FK` llave foránea (tabla.columna referenciada y acción al borrar), `UQ` valor único.
- **Fechas:** `timestamp` sin zona horaria, siempre en **UTC** (la API las devuelve en ISO 8601 y el navegador las convierte a hora local).
- **Valores acotados:** se validan dos veces, en la API (Pydantic, responde `422`) y en la base (`CHECK`), para que ningún otro cliente guarde un valor fuera de la lista.

Resumen de relaciones:

| Relación | Cardinalidad | Al borrar el padre |
|---|---|---|
| `usuarios` → `bitacora_auditoria.usuario_id` | 1 : 0..N | `SET NULL` (la bitácora conserva el nombre en `usuario`) |
| `usuarios` → `datasets.publicado_por_id` | 1 : 0..N | `SET NULL` |
| `usuarios` → `reportes_dataset.atendido_por_id` | 1 : 0..N | `SET NULL` |
| `datasets` → `descargas_datasets.id_dataset` | 1 : 0..1 | `CASCADE` |
| `datasets` → `reportes_dataset.id_dataset` | 1 : 0..N | `CASCADE` |

---

## 1. `usuarios`

Funcionarios con acceso al panel de administración.

| Campo | Tipo | Nulo | Llave | Por defecto | Restricciones | Descripción |
|---|---|---|---|---|---|---|
| `id` | `integer` | NO | PK | autoincremental | | Identificador del funcionario |
| `username` | `varchar(50)` | NO | UQ | | 3 a 50 caracteres (API) | Nombre de usuario para iniciar sesión |
| `password_hash` | `varchar(255)` | NO | | | | Hash Argon2 de la contraseña (nunca se guarda en texto plano ni se devuelve en la API) |
| `rol` | `varchar(20)` | NO | | `'editor'` | `CHECK rol IN ('admin', 'editor')` | `admin`: todo el panel. `editor`: publica, edita y atiende reportes, pero no borra ni administra usuarios |

## 2. `datasets`

Registro relacional del catálogo. ChromaDB guarda el índice de búsqueda (vectores); esta tabla guarda los mismos datasets para que descargas y reportes tengan integridad referencial. Se sincroniza con ChromaDB al arrancar y en cada alta, edición o baja.

| Campo | Tipo | Nulo | Llave | Por defecto | Restricciones | Descripción |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | NO | PK | | UUID | Mismo identificador que en ChromaDB y que el nombre del CSV en `data/raw/` |
| `titulo` | `varchar(200)` | NO | | | | Título visible del dataset |
| `descripcion` | `text` | NO | | | Máx. 2000 caracteres (API) | Descripción en lenguaje ciudadano; se usa para generar el embedding |
| `dependencia` | `varchar(200)` | NO | | | | Dependencia municipal responsable |
| `categoria` | `varchar(100)` | NO | | | `CHECK` en las 10 categorías oficiales (Movilidad, Medio Ambiente, Seguridad, Economía, Infraestructura y Obras, Salud, Desarrollo Social, Administración y Finanzas, Cultura y Deporte, Educación) | Categoría para los filtros del portal |
| `archivo_original` | `varchar(255)` | SÍ | UQ | | | Nombre del CSV entregado por el municipio. Solo los datasets de la carga inicial (`db/seed`); los publicados desde el panel quedan en `NULL` |
| `hash_sha256` | `varchar(64)` | SÍ | UQ | | 64 caracteres hexadecimales | Huella del archivo: impide publicar dos veces el mismo CSV |
| `fecha_actualizacion` | `date` | SÍ | | | | Última vez que cambiaron sus datos o metadatos |
| `publicado_por_id` | `integer` | SÍ | FK → `usuarios.id` (`ON DELETE SET NULL`) | | | Funcionario que lo publicó. `NULL` en la carga inicial |

## 3. `descargas_datasets`

Contador de descargas por dataset (uno por dataset, se crea con la primera descarga).

| Campo | Tipo | Nulo | Llave | Por defecto | Restricciones | Descripción |
|---|---|---|---|---|---|---|
| `id_dataset` | `varchar(36)` | NO | PK, FK → `datasets.id` (`ON DELETE CASCADE`) | | | Dataset contado |
| `total_descargas` | `integer` | NO | | `0` (aplicación) | `CHECK total_descargas >= 0` | Descargas acumuladas, en cualquier formato (CSV, JSON, XML, GeoJSON) |

## 4. `reportes_dataset` (SC-001)

Problemas que reportan los ciudadanos sobre un dataset y su atención por el equipo municipal.

| Campo | Tipo | Nulo | Llave | Por defecto | Restricciones | Descripción |
|---|---|---|---|---|---|---|
| `id` | `integer` | NO | PK | autoincremental | | Folio del reporte (se le muestra al ciudadano) |
| `id_dataset` | `varchar(36)` | NO | FK → `datasets.id` (`ON DELETE CASCADE`) | | | Dataset reportado |
| `tipo` | `varchar(30)` | NO | | | `CHECK tipo IN ('datos_incorrectos', 'desactualizado', 'archivo_danado', 'otro')` | Clase de problema |
| `descripcion` | `text` | NO | | | 10 a 1000 caracteres (API) | Qué está mal y dónde |
| `email_contacto` | `varchar(254)` | SÍ | | | Correo válido (API) | Opcional: para avisar al ciudadano |
| `estado` | `varchar(20)` | NO | | `'abierto'` | `CHECK estado IN ('abierto', 'en_revision', 'resuelto')`. Transiciones (API): `abierto → en_revision → resuelto` o `abierto → resuelto`; no retrocede (`409`) | Estado de atención |
| `fecha_creacion` | `timestamp` | NO | | hora actual (aplicación) | | Momento del reporte (UTC) |
| `fecha_actualizacion` | `timestamp` | SÍ | | | | Último cambio de estado (UTC) |
| `atendido_por_id` | `integer` | SÍ | FK → `usuarios.id` (`ON DELETE SET NULL`) | | | Funcionario que hizo el último cambio de estado |

Índices: `ix_reportes_estado_fecha (estado, fecha_creacion)` para la bandeja del panel (justificación en `objetos_bd.sql`) e `ix_reportes_dataset_id_dataset (id_dataset)` para la llave foránea.

## 5. `bitacora_auditoria`

Registro de las acciones administrativas (publicar, editar, borrar, cambiar el estado de un reporte, altas y bajas de usuarios). Se exporta a CSV desde el panel.

| Campo | Tipo | Nulo | Llave | Por defecto | Restricciones | Descripción |
|---|---|---|---|---|---|---|
| `id` | `integer` | NO | PK | autoincremental | | Identificador del evento |
| `usuario` | `varchar(50)` | NO | | | | Nombre del funcionario al momento del evento. Se conserva aunque la cuenta se borre |
| `usuario_id` | `integer` | SÍ | FK → `usuarios.id` (`ON DELETE SET NULL`) | | | Cuenta del funcionario mientras exista |
| `accion` | `varchar(50)` | NO | | | | Tipo de acción: `Publicación`, `Actualización`, `Eliminación`, `Reporte`, `Creación Usuario`, etc. |
| `detalles` | `text` | NO | | | | Descripción legible del evento |
| `fecha_hora` | `timestamp` | NO | | hora actual (aplicación) | | Momento del evento (UTC). Indexada: el panel muestra los más recientes |

## 6. `mensajes_contacto`

Buzón ciudadano (formulario de contacto del portal).

| Campo | Tipo | Nulo | Llave | Por defecto | Restricciones | Descripción |
|---|---|---|---|---|---|---|
| `id` | `integer` | NO | PK | autoincremental | | Identificador del mensaje |
| `nombre` | `varchar(100)` | NO | | | 3 a 100 caracteres (API) | Nombre del remitente |
| `email` | `varchar(254)` | NO | | | Correo válido (API) | Correo para responder |
| `mensaje` | `text` | NO | | | 10 a 2000 caracteres (API) | Contenido del mensaje |
| `fecha_envio` | `timestamp` | NO | | hora actual (aplicación) | | Momento del envío (UTC) |

---

## Vista `v_resumen_datasets`

Una fila por dataset; no guarda datos, se calcula en cada consulta. Definición y justificación en `objetos_bd.sql`.

| Columna | Tipo | Descripción |
|---|---|---|
| `id`, `titulo`, `categoria`, `dependencia` | igual que en `datasets` | Datos del dataset |
| `total_descargas` | `integer` | Descargas acumuladas (0 si nunca se descargó) |
| `total_reportes` | `bigint` | Reportes recibidos |
| `reportes_pendientes` | `bigint` | Reportes en estado `abierto` o `en_revision` |
| `ultimo_reporte` | `timestamp` | Fecha del reporte más reciente (`NULL` si no tiene) |

## Tabla técnica `alembic_version`

La crea Alembic: guarda la revisión del esquema aplicada (`0002`). No forma parte del modelo de negocio.
