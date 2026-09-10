import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv

router = APIRouter(tags=["Autenticación"])

load_dotenv()

# Configuración de seguridad JWT y Credenciales
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-inseguro")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

# Dependencia para proteger rutas
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
def login_admin(credenciales: CredencialesAdmin):
    # Validamos que las variables de entorno existan por seguridad
    if not ADMIN_USER or not ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de configuración del servidor: Faltan credenciales en el entorno."
        )

    if credenciales.usuario == ADMIN_USER and credenciales.password == ADMIN_PASSWORD:
        tiempo_expiracion = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expira_en = datetime.utcnow() + tiempo_expiracion
        
        payload = {
            "sub": credenciales.usuario,
            "exp": expira_en
        }
        
        token_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        return {
            "access_token": token_jwt,
            "token_type": "bearer"
        }
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario o contraseña incorrectos"
    )