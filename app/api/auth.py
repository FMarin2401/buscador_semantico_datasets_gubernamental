import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv


router = APIRouter(tags=["Autenticación"])

# Configuración de seguridad JWT
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-inseguro")
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
    if credenciales.usuario == "admin" and credenciales.password == "admin123":
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