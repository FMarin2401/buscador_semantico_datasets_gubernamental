from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.db_core.connection import get_db
from app.db_core.models import MensajeContactoModel
from app.db_core.auditoria import registrar_evento_auditoria
from app.api.auth import verificar_token, requiere_admin
from app.limiter import limiter
from app.api.esquemas import MensajeRespuesta, ERROR_401, ERROR_403, ERROR_429, error

router = APIRouter(tags=["Contacto"])

class MensajeSchema(BaseModel):
    nombre: str = Field(min_length=3, max_length=100)
    email: EmailStr
    mensaje: str = Field(min_length=10, max_length=2000)

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "nombre": "María López",
        "email": "maria@ejemplo.com",
        "mensaje": "¿Publicarán los horarios de las rutas de camión?",
    }]})


class MensajeContacto(BaseModel):
    id: int
    nombre: str
    email: str
    mensaje: str
    fecha_envio: datetime = Field(description="UTC")

    model_config = ConfigDict(from_attributes=True)


class ListaMensajes(BaseModel):
    mensajes: list[MensajeContacto]

    model_config = ConfigDict(json_schema_extra={"examples": [{"mensajes": [{
        "id": 3, "nombre": "María López", "email": "maria@ejemplo.com",
        "mensaje": "¿Publicarán los horarios de las rutas de camión?", "fecha_envio": "2026-11-01T17:20:00",
    }]}]})

# Endpoint público para recibir mensajes
@router.post(
    "/api/contacto",
    status_code=status.HTTP_201_CREATED,
    response_model=MensajeRespuesta,
    summary="Enviar un mensaje al buzón ciudadano",
    description="Público. Nombre de 3 a 100 caracteres, correo válido y mensaje de 10 a 2000 caracteres. Límite: 5 mensajes por minuto por IP.",
    responses={429: ERROR_429},
)
@limiter.limit("5/minute")
def enviar_mensaje(request: Request, datos: MensajeSchema, db: Session = Depends(get_db)):
    nuevo_mensaje = MensajeContactoModel(
        nombre=datos.nombre,
        email=datos.email,
        mensaje=datos.mensaje
    )
    db.add(nuevo_mensaje)
    db.commit()
    return {"mensaje": "Mensaje enviado exitosamente"}

# Endpoint protegido para el panel de administración
@router.get(
    "/api/admin/mensajes",
    response_model=ListaMensajes,
    summary="Listar los mensajes del buzón",
    description="Del más reciente al más antiguo. Requiere sesión (administrador o editor).",
    responses={401: ERROR_401},
)
def listar_mensajes(
    usuario_autenticado: str = Depends(verificar_token), 
    db: Session = Depends(get_db)
):
    mensajes = db.query(MensajeContactoModel).order_by(MensajeContactoModel.fecha_envio.desc()).all()
    return {"mensajes": mensajes}

@router.delete(
    "/api/admin/mensajes/{id_mensaje}",
    response_model=MensajeRespuesta,
    summary="Eliminar un mensaje del buzón",
    description="Queda registrado en la bitácora. Solo administradores.",
    responses={401: ERROR_401, 403: ERROR_403, 404: error("El mensaje no existe", "Mensaje no encontrado.")},
)
def eliminar_mensaje(
    id_mensaje: int,
    usuario_autenticado: str = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
    mensaje = db.query(MensajeContactoModel).filter(MensajeContactoModel.id == id_mensaje).first()
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.")

    remitente = mensaje.nombre
    db.delete(mensaje)
    
    # Registro en la bitácora de auditoría
    registrar_evento_auditoria(db, usuario_autenticado, "Eliminación Mensaje", f"Mensaje de {remitente} (ID: {id_mensaje})")
    db.commit()

    return {"mensaje": "Mensaje eliminado exitosamente"}