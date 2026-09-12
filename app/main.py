# Este archivo contiene la logica principal de la API de FastAPI para el buscador semántico gubernamental

# Librerías estándar de Python
import os
import logging

# Librerías de terceros 
from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import manipulate_datasets, pages, search, auth, contact
from passlib.context import CryptContext
from app.db_users.connection import engine, Base, SessionLocal
from app.db_users.models import UsuarioModel

# Configuración de logging para consola y archivo para auditoria
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/auditoria.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(title="API Buscador Semántico Gubernamental") # Crea un servidor FastAPI con el nombre de la API

app.mount("/data", StaticFiles(directory="data/raw"), name="data") # Converte la carpeta data/raw en un servidor de archivos estaticos para descarga
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

app.include_router(pages.router)  # Incluimos las rutas de páginas web desde app/api/pages.py
app.include_router(search.router) # Incluimos las rutas de búsqueda semántica desde app/api/search.py
app.include_router(manipulate_datasets.router) # Incluimos las rutas de gestión de datasets desde app/api/datasets.py
app.include_router(auth.router) # Incluimos las rutas de autenticación desde app/api/auth.py
app.include_router(contact.router)

# Configuración de CORS (solo para desarrollo, en producción se tiene que restringir los orígenes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Passlib para cifrar la contraseña inicial
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Crear la tabla de SQLite automáticamente
Base.metadata.create_all(bind=engine)

# Movemos el monitor de estado
@app.get("/api/status")
def status_check():
    return {"mensaje": "Servidor en línea."}

@app.on_event("startup")
def inicializar_admin():
    db = SessionLocal()
    admin_existente = db.query(UsuarioModel).first()
    if not admin_existente:
        user_env = os.getenv("ADMIN_USER", "admin")
        pass_env = os.getenv("ADMIN_PASSWORD", "secreto123")
        
        nuevo_admin = UsuarioModel(
            username=user_env,
            password_hash=pwd_context.hash(pass_env),
            rol="admin"
        )
        db.add(nuevo_admin)
        db.commit()
        print("¡Administrador inicial registrado en SQLite desde el .env!")
    db.close()