from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from .connection import Base

class UsuarioModel(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    rol = Column(String, default="admin")

class MensajeContactoModel(Base):
    __tablename__ = "mensajes_contacto"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, nullable=False)
    mensaje = Column(Text, nullable=False)
    fecha_envio = Column(DateTime, default=datetime.utcnow)

class BitacoraAuditoriaModel(Base):
    __tablename__ = "bitacora_auditoria"

    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String, nullable=False)          #
    accion = Column(String, nullable=False)           
    detalles = Column(String, nullable=False)         
    fecha_hora = Column(DateTime, default=datetime.utcnow) 

class DescargasDatasetModel(Base):
    __tablename__ = "descargas_datasets"

    id_dataset = Column(String, primary_key=True, index=True) # UUID del dataset
    total_descargas = Column(Integer, default=0, nullable=False)