-- =====================================================================================================
-- Objetos de base de datos (PostgreSQL) del Buscador Semántico de Datasets Gubernamentales
--
-- La migración api/alembic/versions/0002_integridad_y_reportes.py crea estos objetos automáticamente al
-- arrancar la API (docker compose up). Este archivo los documenta y permite crearlos a mano; usa IF NOT EXISTS
-- y CREATE OR REPLACE para poder ejecutarse sobre una base que ya los tiene:
--   docker compose exec -T db psql -U portal -d portal_datos < db/objetos_bd.sql
-- Si cambian, hay que cambiar también la migración (y viceversa).
-- =====================================================================================================


-- -----------------------------------------------------------------------------------------------------
-- ÍNDICE: ix_reportes_estado_fecha
-- -----------------------------------------------------------------------------------------------------
-- Consulta que acelera (bandeja de reportes del panel, GET /api/admin/reportes?estado=abierto):
--     SELECT ... FROM reportes_dataset WHERE estado = 'abierto' ORDER BY fecha_creacion DESC;
--
-- Justificación:
--   * Es la consulta más frecuente del módulo SC-001: el panel la ejecuta cada vez que se abre la pestaña,
--     se cambia el filtro o se atiende un reporte.
--   * Sin índice, PostgreSQL recorre toda la tabla y ordena el resultado en memoria. La tabla solo crece
--     (los reportes resueltos se conservan como historial), así que el costo aumenta con el tiempo, mientras
--     que los reportes pendientes que se consultan son pocos.
--   * El orden de las columnas importa: "estado" primero porque es el filtro de igualdad; "fecha_creacion"
--     después, para que las filas ya salgan ordenadas del índice (PostgreSQL lo recorre en sentido inverso
--     para el DESC) y no haga falta un paso de ordenamiento.
--   * Un índice solo sobre "estado" serviría para filtrar, pero con solo tres valores posibles es poco
--     selectivo y seguiría requiriendo el ordenamiento.
CREATE INDEX IF NOT EXISTS ix_reportes_estado_fecha
    ON reportes_dataset (estado, fecha_creacion);

-- Verificación del plan (con pocos registros PostgreSQL puede preferir leer la tabla completa;
-- con SET enable_seqscan = off se fuerza a mostrar que el índice es utilizable):
--   EXPLAIN SELECT * FROM reportes_dataset WHERE estado = 'abierto' ORDER BY fecha_creacion DESC;


-- -----------------------------------------------------------------------------------------------------
-- VISTA: v_resumen_datasets
-- -----------------------------------------------------------------------------------------------------
-- Una fila por dataset con sus descargas y sus reportes. La consume GET /api/admin/reportes/resumen-datasets
-- (tabla "Datasets con reportes" del panel).
--
-- Justificación:
--   * Junta tres tablas (datasets, descargas_datasets y reportes_dataset) con LEFT JOIN y agregados. Sin la
--     vista, esa lógica viviría en el código de la API y habría que repetirla en cualquier otro consumidor
--     (un reporte para la Unidad de Transparencia, una consulta en psql, una herramienta de BI).
--   * Los LEFT JOIN conservan los datasets sin descargas ni reportes (con 0), y COALESCE evita NULL en los
--     contadores, así que quien la consulta no tiene que conocer esos detalles.
--   * "reportes_pendientes" define en un solo lugar qué cuenta como pendiente (abierto o en revisión).
--   * Es una vista normal, no materializada: siempre refleja los datos actuales y el volumen es pequeño
--     (decenas de datasets), así que calcularla en cada consulta es barato.
CREATE OR REPLACE VIEW v_resumen_datasets AS
SELECT
    d.id,
    d.titulo,
    d.categoria,
    d.dependencia,
    COALESCE(dd.total_descargas, 0) AS total_descargas,
    COUNT(r.id) AS total_reportes,
    COALESCE(SUM(CASE WHEN r.estado IN ('abierto', 'en_revision') THEN 1 ELSE 0 END), 0) AS reportes_pendientes,
    MAX(r.fecha_creacion) AS ultimo_reporte
FROM datasets d
LEFT JOIN descargas_datasets dd ON dd.id_dataset = d.id
LEFT JOIN reportes_dataset r ON r.id_dataset = d.id
GROUP BY d.id, d.titulo, d.categoria, d.dependencia, dd.total_descargas;

-- Ejemplo de uso:
--   SELECT titulo, reportes_pendientes, total_descargas
--   FROM v_resumen_datasets
--   WHERE total_reportes > 0
--   ORDER BY reportes_pendientes DESC;
