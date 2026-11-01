# Solicitudes de cambio

Registro de los cambios de requerimiento del Buscador Semántico de Datasets Gubernamentales.

| Folio | Título | Estado | Fecha de registro |
|---|---|---|---|
| SC-001 | Reportar problemas en un dataset | Implementada | 2026-11-01 |

---

## SC-001: Reportar problemas en un dataset

| Campo | Valor |
|---|---|
| **Folio** | SC-001 |
| **Solicitante** | Unidad de Transparencia del Municipio de León |
| **Fecha de registro** | 2026-11-01 |
| **Prioridad** | Media |
| **Estado** | Implementada (2026-11-01) |
| **Rama / PR** | `feat/modelo-datos-sc001` |

### Descripción

Hoy, si un ciudadano encuentra un error en un dataset (coordenadas equivocadas, información vieja, un archivo que no abre), solo puede escribir al buzón general de contacto. El mensaje no dice de qué dataset se trata, no tiene seguimiento y el equipo no sabe qué conjuntos de datos acumulan más problemas.

**Requerimiento:** desde la ficha técnica de cada dataset, el ciudadano puede reportar un problema indicando su tipo, una descripción y, si quiere, su correo. El equipo municipal atiende los reportes desde el panel de administración, donde cada uno avanza por estados hasta resolverse.

### Reglas de negocio

1. Un reporte siempre pertenece a un dataset que existe. Si el dataset no existe, la API responde `404`.
2. El tipo es uno de: `datos_incorrectos`, `desactualizado`, `archivo_danado`, `otro`.
3. La descripción tiene entre 10 y 1000 caracteres. El correo es opcional, pero si se envía debe ser válido.
4. Todo reporte nace en estado `abierto`.
5. Los estados avanzan y nunca retroceden: `abierto` → `en_revision` → `resuelto`, o directo de `abierto` a `resuelto`. Un reporte `resuelto` queda cerrado. Cualquier otra transición responde `409 Conflict`.
6. Cualquier persona puede reportar, sin sesión, con un límite de 5 reportes por minuto por IP (`429`). Solo los funcionarios con sesión ven y atienden los reportes, y solo un administrador puede borrarlos (`403` para un editor).
7. Cada cambio de estado y cada borrado quedan en la bitácora de auditoría, con el funcionario que lo hizo.
8. Al eliminar un dataset se eliminan también sus reportes.

### Impacto por capa

#### Base de datos

| Cambio | Detalle |
|---|---|
| Tabla nueva `reportes_dataset` | `id` (PK), `id_dataset` (FK → `datasets.id`, `ON DELETE CASCADE`), `tipo` (CHECK), `descripcion`, `email_contacto` (opcional), `estado` (CHECK, por defecto `abierto`), `fecha_creacion`, `fecha_actualizacion`, `atendido_por_id` (FK → `usuarios.id`, `ON DELETE SET NULL`) |
| Tabla nueva `datasets` | Requisito de la SC: un reporte necesita una llave foránea hacia su dataset, y el catálogo solo existía en ChromaDB. La tabla es el registro relacional del catálogo y se sincroniza con ChromaDB al arrancar y en cada alta, edición o baja del panel |
| Índice `ix_reportes_estado_fecha` | `(estado, fecha_creacion)` para la bandeja del panel. Justificación en `db/objetos_bd.sql` |
| Vista `v_resumen_datasets` | Descargas, reportes totales y pendientes por dataset |
| Migración | `api/alembic/versions/0002_integridad_y_reportes.py` (incluye también las FK y los CHECK de las tablas existentes) |

#### API

| Método | Ruta | Acceso | Respuestas |
|---|---|---|---|
| POST | `/api/datasets/{id_dataset}/reportes` | Público (5/min por IP) | `201`, `404`, `422`, `429` |
| GET | `/api/admin/reportes?estado=` | Sesión (admin o editor) | `200`, `401`, `422` |
| GET | `/api/admin/reportes/resumen-datasets` | Sesión | `200`, `401` |
| PATCH | `/api/admin/reportes/{id_reporte}` | Sesión | `200`, `401`, `404`, `409`, `422` |
| DELETE | `/api/admin/reportes/{id_reporte}` | Solo administrador | `200`, `401`, `403`, `404` |

Código en `api/app/api/reportes.py`. Cada endpoint está documentado en `/docs` con su descripción, esquemas, ejemplos y códigos de respuesta.

**Prueba negativa principal:** marcar un reporte como `resuelto` e intentar devolverlo a `abierto` con `PATCH /api/admin/reportes/{id}` → `409 {"detail": "Un reporte resuelto no se puede reabrir ni modificar."}`.

#### Frontend

| Pantalla | Cambio |
|---|---|
| Ficha técnica del dataset (`explorar_datos.html`, `js/busqueda.js`) | Sección «¿Encontraste un problema?» con el formulario de reporte. Muestra el folio al enviarlo y mensajes de error claros para `422`, `429` y fallas de conexión |
| Panel de administración (`admin.html`, `js/admin.js`) | Pestaña «Reportes de Datasets»: filtro por estado, tabla con estados de color, botones solo para las transiciones permitidas, borrado solo para administradores, estados vacío y de error, y la tabla «Datasets con reportes» que lee la vista |

### Verificación

- En docker compose (PostgreSQL): crear un reporte (`201`); tipo inválido (`422`); dataset inexistente (`404`); listar sin sesión (`401`); `abierto` → `en_revision` (`200`); `en_revision` → `abierto` (`409`); `en_revision` → `resuelto` (`200`); `resuelto` → `abierto` (`409`); reporte inexistente (`404`).
- Un `INSERT` directo con `estado = 'cerrado'` lo rechaza el CHECK `ck_reportes_estado`.
- Al borrar un dataset desde el panel se borran su contador de descargas y sus reportes.
- En Chromium: envío desde la ficha con folio, validación nativa de la descripción corta, bandeja del panel, cambio de estado con aviso, filtro por estado; sin errores de consola y sin desborde horizontal en móvil.
- La migración 0002 se aplicó también sobre una copia de una base SQLite existente (esquema 0001 con datos), y se probaron el downgrade y el nuevo upgrade.
