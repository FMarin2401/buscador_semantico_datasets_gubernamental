from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import Literal

from app.db_core.connection import get_db
from app.db_core.models import UsuarioModel
from app.db_core.auditoria import registrar_evento_auditoria
from app.api.auth import requiere_admin
from app.security import cifrar_password
from app.api.esquemas import MensajeRespuesta, ERROR_401, ERROR_403, error

router = APIRouter(tags=["Administración de Usuarios"])

class NuevoUsuarioSchema(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=72)
    rol: Literal["admin", "editor"] = "editor"

    model_config = ConfigDict(json_schema_extra={"examples": [{"username": "jperez", "password": "Temporal_2026", "rol": "editor"}]})


class UsuarioResumen(BaseModel):
    id: int
    username: str
    rol: Literal["admin", "editor"]


class ListaUsuarios(BaseModel):
    usuarios: list[UsuarioResumen]

    model_config = ConfigDict(json_schema_extra={"examples": [{"usuarios": [
        {"id": 1, "username": "admin_leon", "rol": "admin"},
        {"id": 2, "username": "jperez", "rol": "editor"},
    ]}]})


@router.get(
    "/api/admin/usuarios",
    response_model=ListaUsuarios,
    summary="Listar funcionarios",
    description="Cuentas con acceso al panel (sin contraseñas). Solo administradores.",
    responses={401: ERROR_401, 403: ERROR_403},
)
def listar_usuarios(
    usuario_autenticado: str = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
    usuarios = db.query(UsuarioModel).all()
    return {
        "usuarios": [
            {"id": u.id, "username": u.username, "rol": u.rol}
            for u in usuarios
        ]
    }

@router.post(
    "/api/admin/usuarios",
    status_code=status.HTTP_201_CREATED,
    response_model=MensajeRespuesta,
    summary="Dar de alta un funcionario",
    description="La contraseña se guarda cifrada con Argon2. El rol solo puede ser `admin` o `editor`. Solo administradores.",
    responses={401: ERROR_401, 403: ERROR_403, 409: error("El nombre de usuario ya existe", "El nombre de usuario ya existe en el sistema.")},
)
def crear_usuario(
    datos: NuevoUsuarioSchema,
    usuario_autenticado: str = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
    existe = db.query(UsuarioModel).filter(UsuarioModel.username == datos.username.strip()).first()
    if existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya existe en el sistema."
        )

    password_cifrado = cifrar_password(datos.password)

    nuevo_admin = UsuarioModel(
        username=datos.username.strip(),
        password_hash=password_cifrado,
        rol=datos.rol
    )
    db.add(nuevo_admin)

    registrar_evento_auditoria(db, usuario_autenticado, "Creación Usuario", f"Alta de funcionario '{datos.username}' con rol '{datos.rol}'")
    db.commit()

    return {"mensaje": "Usuario creado exitosamente"}

@router.delete(
    "/api/admin/usuarios/{id_usuario}",
    response_model=MensajeRespuesta,
    summary="Dar de baja un funcionario",
    description="Un administrador no puede borrar su propia cuenta. La bitácora conserva el nombre de la cuenta borrada. Solo administradores.",
    responses={
        400: error("Intento de borrar la propia cuenta", "No puedes eliminar tu propia cuenta mientras estás en sesión."),
        401: ERROR_401,
        403: ERROR_403,
        404: error("El usuario no existe", "Usuario no encontrado."),
    },
)
def eliminar_usuario(
    id_usuario: int,
    usuario_autenticado: str = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
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

    registrar_evento_auditoria(db, usuario_autenticado, "Baja Usuario", f"Eliminación de funcionario '{nombre}'")
    db.commit()

    return {"mensaje": f"Usuario '{nombre}' eliminado"}