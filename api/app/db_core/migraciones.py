# Este archivo aplica las migraciones de Alembic a la base relacional (SQLite en local, PostgreSQL en produccion)

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db_core.connection import engine

logger = logging.getLogger(__name__)

RUTA_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
REVISION_INICIAL = "0001" # Esquema que creaba Base.metadata.create_all() antes de usar Alembic


def aplicar_migraciones():
    config = Config(str(RUTA_ALEMBIC_INI))
    config.attributes["configurar_logging"] = False # La app ya configuro su logging en main.py

    tablas = inspect(engine).get_table_names()
    if "usuarios" in tablas and "alembic_version" not in tablas:
        # Base creada antes de Alembic: ya tiene el esquema inicial, solo falta registrarlo.
        # Sin esto, Alembic intentaria crear tablas que ya existen y fallaria.
        logger.info("Base existente sin control de versiones: se marca como revision %s", REVISION_INICIAL)
        command.stamp(config, REVISION_INICIAL)

    command.upgrade(config, "head")
