from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.catalogo import CATEGORIAS
from app.db_core.connection import Base

# Valores acotados. Se validan en la API (Pydantic) y también en la base (CHECK), para que ningún otro cliente
# (un script, una consulta manual) pueda guardar un valor fuera de la lista
ROLES = ("admin", "editor")
TIPOS_REPORTE = ("datos_incorrectos", "desactualizado", "archivo_danado", "otro")
ESTADOS_REPORTE = ("abierto", "en_revision", "resuelto")
ESTADOS_PENDIENTES = ("abierto", "en_revision")

def lista_sql(valores) -> str:
    return ", ".join(f"'{v}'" for v in valores)

def ahora_utc():
    # Reemplaza a datetime.utcnow (obsoleto desde Python 3.12). Se guarda sin zona horaria,
    # igual que antes, porque las columnas son DateTime sin zona y la exportación ya las marca como UTC
    return datetime.now(timezone.utc).replace(tzinfo=None)

class UsuarioModel(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint(f"rol IN ({lista_sql(ROLES)})", name="ck_usuarios_rol"),)

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), nullable=False, default="editor", server_default="editor")

class MensajeContactoModel(Base):
    __tablename__ = "mensajes_contacto"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(254), nullable=False)
    mensaje = Column(Text, nullable=False)
    fecha_envio = Column(DateTime, nullable=False, default=ahora_utc)

class BitacoraAuditoriaModel(Base):
    __tablename__ = "bitacora_auditoria"

    id = Column(Integer, primary_key=True, index=True)
    # El nombre se guarda tal cual aunque el usuario se borre después: la bitácora conserva quién hizo cada acción.
    # usuario_id liga el evento con la cuenta mientras exista (al borrarla queda en NULL)
    usuario = Column(String(50), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL", name="fk_bitacora_usuario"), nullable=True, index=True)
    accion = Column(String(50), nullable=False)
    detalles = Column(Text, nullable=False)
    fecha_hora = Column(DateTime, nullable=False, default=ahora_utc, index=True) # El panel muestra los últimos eventos

class DatasetModel(Base):
    """
    Registro relacional del catálogo. ChromaDB sigue siendo el índice de búsqueda (vectores y metadatos); esta tabla
    guarda los mismos datasets para que descargas y reportes tengan integridad referencial. Se sincroniza con ChromaDB
    al arrancar (app/db_core/sincronizacion.py) y en cada alta, edición o baja desde el panel.
    """
    __tablename__ = "datasets"
    __table_args__ = (CheckConstraint(f"categoria IN ({lista_sql(CATEGORIAS)})", name="ck_datasets_categoria"),)

    id = Column(String(36), primary_key=True) # Mismo UUID que en ChromaDB y que el nombre del CSV en data/raw
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=False)
    dependencia = Column(String(200), nullable=False)
    categoria = Column(String(100), nullable=False)
    archivo_original = Column(String(255), unique=True, nullable=True) # Solo los del catálogo inicial (db/seed)
    hash_sha256 = Column(String(64), unique=True, nullable=True) # Impide publicar dos veces el mismo archivo
    fecha_actualizacion = Column(Date, nullable=True)
    publicado_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL", name="fk_datasets_publicado_por"), nullable=True)

    # El ORM borra también las descargas y los reportes (en PostgreSQL además lo hace ON DELETE CASCADE)
    descargas = relationship("DescargasDatasetModel", cascade="all, delete-orphan")
    reportes = relationship("ReporteDatasetModel", cascade="all, delete-orphan", back_populates="dataset")

class DescargasDatasetModel(Base):
    __tablename__ = "descargas_datasets"
    __table_args__ = (CheckConstraint("total_descargas >= 0", name="ck_descargas_no_negativas"),)

    id_dataset = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE", name="fk_descargas_dataset"), primary_key=True, index=True)
    total_descargas = Column(Integer, default=0, nullable=False)

class ReporteDatasetModel(Base):
    """SC-001: problemas que reportan los ciudadanos sobre un dataset (datos incorrectos, desactualizados...)."""
    __tablename__ = "reportes_dataset"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({lista_sql(TIPOS_REPORTE)})", name="ck_reportes_tipo"),
        CheckConstraint(f"estado IN ({lista_sql(ESTADOS_REPORTE)})", name="ck_reportes_estado"),
        # Bandeja del panel: filtra por estado y ordena del más reciente al más antiguo (ver db/objetos_bd.sql)
        Index("ix_reportes_estado_fecha", "estado", "fecha_creacion"),
    )

    id = Column(Integer, primary_key=True)
    id_dataset = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE", name="fk_reportes_dataset"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)
    descripcion = Column(Text, nullable=False)
    email_contacto = Column(String(254), nullable=True) # Opcional: el ciudadano decide si quiere respuesta
    estado = Column(String(20), nullable=False, default="abierto", server_default="abierto")
    fecha_creacion = Column(DateTime, nullable=False, default=ahora_utc)
    fecha_actualizacion = Column(DateTime, nullable=True)
    atendido_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL", name="fk_reportes_atendido_por"), nullable=True)

    dataset = relationship("DatasetModel", back_populates="reportes")
    atendido_por = relationship("UsuarioModel")
