import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.db_core.connection import get_db
from app.db_core.models import UsuarioModel
from app.limiter import limiter

router = APIRouter(tags=["Autenticación"])
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está configurada.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

ES_PRODUCCION = os.getenv("ENVIRONMENT", "local").lower() == "production"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verificar_token(request: Request) -> str:
    """Verifica la validez del token JWT almacenado en la cookie HTTP-only."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se encontró la sesión activa",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario: str = payload.get("sub")
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return usuario
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado o inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def requiere_admin(usuario: str = Depends(verificar_token), db: Session = Depends(get_db)) -> str:
    u = db.query(UsuarioModel).filter(UsuarioModel.username == usuario).first()
    if not u or u.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: se requiere rol de administrador."
        )
    return usuario


class CredencialesAdmin(BaseModel):
    usuario: str
    password: str


@router.post("/api/login")
@limiter.limit("5/minute")
def login_admin(request: Request, response: Response, credenciales: CredencialesAdmin, db: Session = Depends(get_db)):
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
        "rol": usuario_db.rol,
        "exp": expira_en
    }

    token_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    response.set_cookie(
        key="access_token",
        value=token_jwt,
        httponly=True,
        secure=ES_PRODUCCION,   
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

    return {"mensaje": "Autenticación exitosa"}


@router.post("/api/logout")
def logout(response: Response):
    """Cierra la sesión destruyendo la cookie HTTP-only."""
    response.delete_cookie(key="access_token")
    return {"mensaje": "Sesión cerrada exitosamente"}


@router.get("/api/auth/me")
def obtener_usuario_actual(usuario: str = Depends(verificar_token), db: Session = Depends(get_db)):
    """Devuelve el rol y usuario autenticado leyendo la cookie HTTP-only."""
    u = db.query(UsuarioModel).filter(UsuarioModel.username == usuario).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return {
        "username": u.username,
        "rol": u.rol
    }