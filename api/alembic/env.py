# Este archivo configura Alembic para que use la misma conexion y los mismos modelos que la aplicacion

from logging.config import fileConfig

from alembic import context

from app.db_core.connection import engine, Base
import app.db_core.models  # noqa: F401  Registra las tablas en Base.metadata para que Alembic las conozca

config = context.config

# Solo configuramos el logging de alembic.ini cuando se usa desde la terminal;
# si lo llama la app al arrancar, se respeta la configuracion de logging de main.py
if config.config_file_name is not None and config.attributes.get("configurar_logging", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL de las migraciones sin conectarse a la base (alembic upgrade head --sql)."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=engine.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite no soporta ALTER TABLE completo; el modo batch recrea la tabla para cambios como quitar columnas
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
