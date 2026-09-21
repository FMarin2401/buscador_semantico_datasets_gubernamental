# Este archivo contiene la logica principal de la API de FastAPI para el buscador semántico gubernamental

# Librerías estándar de Python
import os
import logging

# Librerías de terceros 
from fastapi import FastAPI, Response, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy import text
from passlib.context import CryptContext

# Módulos internos de la aplicación
from app.api import manipulate_datasets, pages, search, auth, contact
from app.db_users.connection import engine, Base, SessionLocal, get_db
from app.db_users.models import UsuarioModel
from app.nlp_model import generar_embedding
from app.db_chroma import coleccion
from app.limiter import limiter

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

app = FastAPI(title="API Buscador Semántico Gubernamental")

# --- CONTROL GLOBAL DE ESTADO (HEALTH PROBES) ---
app_state = {
    "warmup_ready": False
}

# --- RATE LIMITING ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Servidores de archivos estáticos
app.mount("/data", StaticFiles(directory="data/raw"), name="data")
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

# Registro modular de rutas
app.include_router(pages.router)
app.include_router(search.router)
app.include_router(manipulate_datasets.router)
app.include_router(auth.router)
app.include_router(contact.router)

# Configuración de CORS
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


# --- ENDPOINTS DE MONITOREO Y HEALTH CHECKS ---

@app.get("/api/status", tags=["Monitoreo"])
def status_check():
    """Monitor básico original de estado."""
    return {"mensaje": "Servidor en línea."}

@app.get("/api/health/live", tags=["Monitoreo"])
def liveness_check():
    """Liveness Probe: Comprueba que Uvicorn esté vivo y despachando peticiones."""
    return {"status": "alive"}

@app.get("/api/health/ready", tags=["Monitoreo"])
def readiness_check(response: Response, db: Session = Depends(get_db)):
    """
    Readiness Probe: Comprueba que el warm-up haya concluido,
    que ChromaDB esté en RAM y que SQLite responda consultas.
    """
    errores = []

    # 1. Validar que el warm-up del modelo terminó
    if not app_state["warmup_ready"]:
        errores.append("Warm-up del modelo semántico o ChromaDB en progreso.")

    # 2. Validar conexión a SQLite
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        errores.append(f"SQLite no disponible: {str(e)}")

    if errores:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "ready": False,
            "errores": errores
        }

    return {
        "status": "ready",
        "ready": True,
        "components": {
            "sqlite": "ok",
            "nlp_chromadb": "ok"
        }
    }


# --- CICLO DE VIDA (STARTUP) ---

@app.on_event("startup")
def inicializar_admin():
    db = SessionLocal()
    try:
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
    finally:
        db.close()

    # --- WARM-UP ---
    try:
        vector_test = generar_embedding("warm up test municipal")
        coleccion.query(query_embeddings=[vector_test], n_results=1)
        app_state["warmup_ready"] = True
        print("[WARM-UP] Modelo semántico y ChromaDB precargados exitosamente en RAM.")
    except Exception as e:
        app_state["warmup_ready"] = False
        print(f"[WARM-UP] Aviso durante precarga del modelo: {e}")