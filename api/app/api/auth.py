import os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import APIKeyCookie
from pydantic import BaseModel, ConfigDict, Field
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.db_core.connection import get_db
from app.db_core.models import UsuarioModel
from app.limiter import limiter
from app.api.esquemas import MensajeRespuesta, ERROR_401, ERROR_429, error
from app.security import verificar_password

router = APIRouter(tags=["Autenticación"])
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está configurada.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

ES_PRODUCCION = os.getenv("ENVIRONMENT", "local").lower() == "production"


# Declara en OpenAPI cómo se autentica la API: un JWT en la cookie HttpOnly "access_token" que crea POST /api/login.
# En /docs basta con ejecutar primero /api/login: el navegador guarda la cookie y la envía en las siguientes pruebas.
# auto_error=False para responder con los mensajes propios de verificar_token
esquema_cookie = APIKeyCookie(
    name="access_token",
    auto_error=False,
    description="JWT de sesión (30 min) en una cookie HttpOnly. Se obtiene con POST /api/login.",
)


def verificar_token(token: str | None = Depends(esquema_cookie)) -> str:
    """Verifica la validez del token JWT almacenado en la cookie HTTP-only."""
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
    except jwt.InvalidTokenError: # Incluye token expirado, firma inválida y token mal formado
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
    usuario: str = Field(..., max_length=50)
    password: str = Field(..., max_length=128) # Evita contraseñas enormes que solo gastan CPU al calcular el hash

    model_config = ConfigDict(json_schema_extra={"examples": [{"usuario": "admin_leon", "password": "Admin_Leon_2026"}]})


class UsuarioActual(BaseModel):
    username: str
    rol: str = Field(description="admin | editor")

    model_config = ConfigDict(json_schema_extra={"examples": [{"username": "admin_leon", "rol": "admin"}]})


@router.post(
    "/api/login",
    response_model=MensajeRespuesta,
    summary="Iniciar sesión",
    description=(
        "Valida usuario y contraseña y guarda un JWT de 30 minutos en la cookie HttpOnly `access_token` "
        "(no se devuelve en el cuerpo, así un script inyectado no puede leerlo). Límite: 5 intentos por minuto por IP. "
        "Con los valores de `.env.example`: usuario `admin_leon`, contraseña `Admin_Leon_2026`."
    ),
    responses={401: error("Usuario o contraseña incorrectos", "Usuario o contraseña incorrectos"), 429: ERROR_429},
)
@limiter.limit("5/minute")
def login_admin(request: Request, response: Response, credenciales: CredencialesAdmin, db: Session = Depends(get_db)):
    usuario_db = db.query(UsuarioModel).filter(UsuarioModel.username == credenciales.usuario).first()

    # Siempre se calcula un hash (aunque el usuario no exista) para que el tiempo de respuesta no revele qué usuarios existen
    es_valida, hash_nuevo = verificar_password(
        credenciales.password,
        usuario_db.password_hash if usuario_db else None
    )

    if not es_valida:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos"
        )

    if hash_nuevo:
        # El hash era antiguo (bcrypt): se reemplaza por uno Argon2 aprovechando que tenemos la contraseña en texto plano
        usuario_db.password_hash = hash_nuevo
        db.commit()

    tiempo_expiracion = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expira_en = datetime.now(timezone.utc) + tiempo_expiracion

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


@router.post(
    "/api/logout",
    response_model=MensajeRespuesta,
    summary="Cerrar sesión",
    description="Borra la cookie de sesión. No requiere sesión: sin cookie, simplemente no hay nada que borrar.",
)
def logout(response: Response):
    """Cierra la sesión destruyendo la cookie HTTP-only."""
    response.delete_cookie(key="access_token")
    return {"mensaje": "Sesión cerrada exitosamente"}


@router.get(
    "/api/auth/me",
    response_model=UsuarioActual,
    summary="Usuario de la sesión",
    description="Usuario y rol de la sesión actual. El panel lo usa para mostrar u ocultar las opciones de administrador.",
    responses={401: ERROR_401, 404: error("La cuenta de la sesión ya no existe", "Usuario no encontrado")},
)
def obtener_usuario_actual(usuario: str = Depends(verificar_token), db: Session = Depends(get_db)):
    """Devuelve el rol y usuario autenticado leyendo la cookie HTTP-only."""
    u = db.query(UsuarioModel).filter(UsuarioModel.username == usuario).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return {
        "username": u.username,
        "rol": u.rol
    }