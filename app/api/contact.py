from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.db_users.connection import get_db
from app.db_users.models import MensajeContactoModel, BitacoraAuditoriaModel
from app.api.auth import verificar_token

router = APIRouter(tags=["Contacto"])

class MensajeSchema(BaseModel):
    nombre: str
    email: EmailStr
    mensaje: str

# Endpoint público para recibir mensajes
@router.post("/api/contacto", status_code=status.HTTP_201_CREATED)
def enviar_mensaje(datos: MensajeSchema, db: Session = Depends(get_db)):
    nuevo_mensaje = MensajeContactoModel(
        nombre=datos.nombre,
        email=datos.email,
        mensaje=datos.mensaje
    )
    db.add(nuevo_mensaje)
    db.commit()
    return {"mensaje": "Mensaje enviado exitosamente"}

# Endpoint protegido para el panel de administración
@router.get("/api/admin/mensajes")
def listar_mensajes(
    usuario_autenticado: str = Depends(verificar_token), 
    db: Session = Depends(get_db)
):
    mensajes = db.query(MensajeContactoModel).order_by(MensajeContactoModel.fecha_envio.desc()).all()
    return {"mensajes": mensajes}

@router.delete("/api/admin/mensajes/{id_mensaje}")
def eliminar_mensaje(
    id_mensaje: int,
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    mensaje = db.query(MensajeContactoModel).filter(MensajeContactoModel.id == id_mensaje).first()
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.")

    remitente = mensaje.nombre
    db.delete(mensaje)
    
    # Registro en la bitácora de auditoría
    log_auditoria = BitacoraAuditoriaModel(
        usuario=usuario_autenticado,
        accion="Eliminación Mensaje",
        detalles=f"Mensaje de {remitente} (ID: {id_mensaje})"
    )
    db.add(log_auditoria)
    db.commit()

    return {"mensaje": "Mensaje eliminado exitosamente"}