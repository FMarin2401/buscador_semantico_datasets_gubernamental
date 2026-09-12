import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.db_users.connection import get_db
from app.db_users.models import UsuarioModel, BitacoraAuditoriaModel

router = APIRouter(tags=["Autenticación"])
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-inseguro")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario: str = payload.get("sub")
        if usuario is None:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expirado o inválido")
    return usuario

class CredencialesAdmin(BaseModel):
    usuario: str
    password: str

@router.post("/api/login")
def login_admin(credenciales: CredencialesAdmin, db: Session = Depends(get_db)):
    # Buscamos al usuario en SQLite
    usuario_db = db.query(UsuarioModel).filter(UsuarioModel.username == credenciales.usuario).first()
    
    if not usuario_db or not pwd_context.verify(credenciales.password, usuario_db.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )

    tiempo_expiracion = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expira_en = datetime.utcnow() + tiempo_expiracion
    
    payload = {
        "sub": usuario_db.username,
        "exp": expira_en
    }
    
    token_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    return {
        "access_token": token_jwt,
        "token_type": "bearer"
    }

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
    # Nunca retornar el hash del password
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
    # Validar que quien ejecuta la acción sea realmente ADMIN
    solicitante = db.query(UsuarioModel).filter(UsuarioModel.username == usuario_autenticado).first()
    if not solicitante or solicitante.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: solo administradores pueden gestionar cuentas."
        )
    # Validar no duplicados
    existe = db.query(UsuarioModel).filter(UsuarioModel.username == datos.username.strip()).first()
    if existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya existe en el sistema."
        )

    # Hashear contraseña con bcrypt
    password_cifrado = pwd_context.hash(datos.password)

    nuevo_admin = UsuarioModel(
        username=datos.username.strip(),
        password_hash=password_cifrado,
        rol=datos.rol
    )
    db.add(nuevo_admin)

    # Auditoría
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
    # Validar rol de administrador
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