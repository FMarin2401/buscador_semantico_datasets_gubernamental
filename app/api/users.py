from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db_core.connection import get_db
from app.db_core.models import UsuarioModel, BitacoraAuditoriaModel
from app.api.auth import verificar_token, pwd_context

router = APIRouter(tags=["Administración de Usuarios"])

class NuevoUsuarioSchema(BaseModel):
    username: str
    password: str
    rol: str = "admin"

@router.get("/api/admin/usuarios")
def listar_usuarios(
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    usuarios = db.query(UsuarioModel).all()
    return {
        "usuarios": [
            {"id": u.id, "username": u.username, "rol": u.rol}
            for u in usuarios
        ]
    }

@router.post("/api/admin/usuarios", status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: NuevoUsuarioSchema,
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    solicitante = db.query(UsuarioModel).filter(UsuarioModel.username == usuario_autenticado).first()
    if not solicitante or solicitante.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: solo administradores pueden gestionar cuentas."
        )

    existe = db.query(UsuarioModel).filter(UsuarioModel.username == datos.username.strip()).first()
    if existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya existe en el sistema."
        )

    password_cifrado = pwd_context.hash(datos.password)

    nuevo_admin = UsuarioModel(
        username=datos.username.strip(),
        password_hash=password_cifrado,
        rol=datos.rol
    )
    db.add(nuevo_admin)

    log = BitacoraAuditoriaModel(
        usuario=usuario_autenticado,
        accion="Creación Usuario",
        detalles=f"Alta de funcionario '{datos.username}' con rol '{datos.rol}'"
    )
    db.add(log)
    db.commit()

    return {"mensaje": "Usuario creado exitosamente"}

@router.delete("/api/admin/usuarios/{id_usuario}")
def eliminar_usuario(
    id_usuario: int,
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    solicitante = db.query(UsuarioModel).filter(UsuarioModel.username == usuario_autenticado).first()
    if not solicitante or solicitante.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: solo administradores pueden eliminar cuentas."
        )

    usuario_a_borrar = db.query(UsuarioModel).filter(UsuarioModel.id == id_usuario).first()
    if not usuario_a_borrar:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if usuario_a_borrar.username == usuario_autenticado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta mientras estás en sesión."
        )

    nombre = usuario_a_borrar.username
    db.delete(usuario_a_borrar)

    log = BitacoraAuditoriaModel(
        usuario=usuario_autenticado,
        accion="Baja Usuario",
        detalles=f"Eliminación de funcionario '{nombre}'"
    )
    db.add(log)
    db.commit()

    return {"mensaje": f"Usuario '{nombre}' eliminado"}