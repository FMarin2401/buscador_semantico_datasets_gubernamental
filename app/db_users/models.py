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