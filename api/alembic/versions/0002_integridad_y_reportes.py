"""integridad referencial, tabla datasets y reportes (SC-001)

- usuarios: longitudes, rol obligatorio y acotado (CHECK).
- mensajes_contacto y bitacora_auditoria: longitudes y fechas obligatorias; la bitácora se liga a usuarios (FK).
- datasets: registro relacional del catálogo que indexa ChromaDB (lo llena app/db_core/sincronizacion.py al arrancar).
- descargas_datasets: FK a datasets. Los contadores de datasets que aún no están en la tabla se descartan,
  porque la tabla datasets nace vacía (en Azure la base es efímera y en docker compose empieza vacía).
- reportes_dataset (SC-001), con su índice por estado y fecha.
- Vista v_resumen_datasets. El índice y la vista están documentados en db/objetos_bd.sql.

Las listas de valores se escriben aquí a mano (no se importan de app/): una migración debe seguir produciendo el
mismo esquema aunque el código cambie después.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIAS = (
    "'Movilidad', 'Medio Ambiente', 'Seguridad', 'Economía', 'Infraestructura y Obras', 'Salud', "
    "'Desarrollo Social', 'Administración y Finanzas', 'Cultura y Deporte', 'Educación'"
)

VISTA_RESUMEN = """
CREATE VIEW v_resumen_datasets AS
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
GROUP BY d.id, d.titulo, d.categoria, d.dependencia, dd.total_descargas
"""


def upgrade() -> None:
    # --- usuarios ---
    op.execute("UPDATE usuarios SET rol = 'editor' WHERE rol IS NULL OR rol NOT IN ('admin', 'editor')")
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.alter_column('username', existing_type=sa.String(), type_=sa.String(50), existing_nullable=False)
        batch_op.alter_column('password_hash', existing_type=sa.String(), type_=sa.String(255), existing_nullable=False)
        batch_op.alter_column('rol', existing_type=sa.String(), type_=sa.String(20), nullable=False, server_default='editor')
        batch_op.create_check_constraint('ck_usuarios_rol', "rol IN ('admin', 'editor')")

    # --- mensajes_contacto ---
    op.execute("UPDATE mensajes_contacto SET fecha_envio = CURRENT_TIMESTAMP WHERE fecha_envio IS NULL")
    with op.batch_alter_table('mensajes_contacto', schema=None) as batch_op:
        batch_op.alter_column('nombre', existing_type=sa.String(), type_=sa.String(100), existing_nullable=False)
        batch_op.alter_column('email', existing_type=sa.String(), type_=sa.String(254), existing_nullable=False)
        batch_op.alter_column('fecha_envio', existing_type=sa.DateTime(), nullable=False)

    # --- bitacora_auditoria ---
    op.execute("UPDATE bitacora_auditoria SET fecha_hora = CURRENT_TIMESTAMP WHERE fecha_hora IS NULL")
    with op.batch_alter_table('bitacora_auditoria', schema=None) as batch_op:
        batch_op.add_column(sa.Column('usuario_id', sa.Integer(), nullable=True))
        batch_op.alter_column('usuario', existing_type=sa.String(), type_=sa.String(50), existing_nullable=False)
        batch_op.alter_column('accion', existing_type=sa.String(), type_=sa.String(50), existing_nullable=False)
        batch_op.alter_column('detalles', existing_type=sa.String(), type_=sa.Text(), existing_nullable=False)
        batch_op.alter_column('fecha_hora', existing_type=sa.DateTime(), nullable=False)
        batch_op.create_foreign_key('fk_bitacora_usuario', 'usuarios', ['usuario_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index(batch_op.f('ix_bitacora_auditoria_usuario_id'), ['usuario_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_bitacora_auditoria_fecha_hora'), ['fecha_hora'], unique=False)
    # Los eventos anteriores se ligan con la cuenta que todavía exista con ese nombre
    op.execute(
        "UPDATE bitacora_auditoria SET usuario_id = "
        "(SELECT u.id FROM usuarios u WHERE u.username = bitacora_auditoria.usuario)"
    )

    # --- datasets ---
    op.create_table('datasets',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('titulo', sa.String(200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('dependencia', sa.String(200), nullable=False),
        sa.Column('categoria', sa.String(100), nullable=False),
        sa.Column('archivo_original', sa.String(255), nullable=True),
        sa.Column('hash_sha256', sa.String(64), nullable=True),
        sa.Column('fecha_actualizacion', sa.Date(), nullable=True),
        sa.Column('publicado_por_id', sa.Integer(), nullable=True),
        sa.CheckConstraint(f"categoria IN ({CATEGORIAS})", name='ck_datasets_categoria'),
        sa.ForeignKeyConstraint(['publicado_por_id'], ['usuarios.id'], name='fk_datasets_publicado_por', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('archivo_original', name='uq_datasets_archivo_original'),
        sa.UniqueConstraint('hash_sha256', name='uq_datasets_hash_sha256'),
    )

    # --- descargas_datasets ---
    op.execute("DELETE FROM descargas_datasets WHERE id_dataset NOT IN (SELECT id FROM datasets)")
    with op.batch_alter_table('descargas_datasets', schema=None) as batch_op:
        batch_op.alter_column('id_dataset', existing_type=sa.String(), type_=sa.String(36), existing_nullable=False)
        batch_op.create_foreign_key('fk_descargas_dataset', 'datasets', ['id_dataset'], ['id'], ondelete='CASCADE')
        batch_op.create_check_constraint('ck_descargas_no_negativas', 'total_descargas >= 0')

    # --- reportes_dataset (SC-001) ---
    op.create_table('reportes_dataset',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_dataset', sa.String(36), nullable=False),
        sa.Column('tipo', sa.String(30), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('email_contacto', sa.String(254), nullable=True),
        sa.Column('estado', sa.String(20), server_default='abierto', nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
        sa.Column('fecha_actualizacion', sa.DateTime(), nullable=True),
        sa.Column('atendido_por_id', sa.Integer(), nullable=True),
        sa.CheckConstraint("tipo IN ('datos_incorrectos', 'desactualizado', 'archivo_danado', 'otro')", name='ck_reportes_tipo'),
        sa.CheckConstraint("estado IN ('abierto', 'en_revision', 'resuelto')", name='ck_reportes_estado'),
        sa.ForeignKeyConstraint(['id_dataset'], ['datasets.id'], name='fk_reportes_dataset', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['atendido_por_id'], ['usuarios.id'], name='fk_reportes_atendido_por', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reportes_dataset_id_dataset', 'reportes_dataset', ['id_dataset'], unique=False)
    op.create_index('ix_reportes_estado_fecha', 'reportes_dataset', ['estado', 'fecha_creacion'], unique=False)

    op.execute(VISTA_RESUMEN)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_resumen_datasets")

    op.drop_index('ix_reportes_estado_fecha', table_name='reportes_dataset')
    op.drop_index('ix_reportes_dataset_id_dataset', table_name='reportes_dataset')
    op.drop_table('reportes_dataset')

    with op.batch_alter_table('descargas_datasets', schema=None) as batch_op:
        batch_op.drop_constraint('ck_descargas_no_negativas', type_='check')
        batch_op.drop_constraint('fk_descargas_dataset', type_='foreignkey')
        batch_op.alter_column('id_dataset', existing_type=sa.String(36), type_=sa.String(), existing_nullable=False)

    op.drop_table('datasets')

    with op.batch_alter_table('bitacora_auditoria', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bitacora_auditoria_fecha_hora'))
        batch_op.drop_index(batch_op.f('ix_bitacora_auditoria_usuario_id'))
        batch_op.drop_constraint('fk_bitacora_usuario', type_='foreignkey')
        batch_op.alter_column('fecha_hora', existing_type=sa.DateTime(), nullable=True)
        batch_op.alter_column('detalles', existing_type=sa.Text(), type_=sa.String(), existing_nullable=False)
        batch_op.alter_column('accion', existing_type=sa.String(50), type_=sa.String(), existing_nullable=False)
        batch_op.alter_column('usuario', existing_type=sa.String(50), type_=sa.String(), existing_nullable=False)
        batch_op.drop_column('usuario_id')

    with op.batch_alter_table('mensajes_contacto', schema=None) as batch_op:
        batch_op.alter_column('fecha_envio', existing_type=sa.DateTime(), nullable=True)
        batch_op.alter_column('email', existing_type=sa.String(254), type_=sa.String(), existing_nullable=False)
        batch_op.alter_column('nombre', existing_type=sa.String(100), type_=sa.String(), existing_nullable=False)

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_constraint('ck_usuarios_rol', type_='check')
        batch_op.alter_column('rol', existing_type=sa.String(20), type_=sa.String(), nullable=True, server_default=None)
        batch_op.alter_column('password_hash', existing_type=sa.String(255), type_=sa.String(), existing_nullable=False)
        batch_op.alter_column('username', existing_type=sa.String(50), type_=sa.String(), existing_nullable=False)
