# Este archivo contiene la logica principal de la API de FastAPI para el buscador semántico gubernamental

# Librerías estándar de Python
import os
import logging
from contextlib import asynccontextmanager

# Librerías de terceros
from fastapi import FastAPI, Response, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy import text

# Módulos internos de la aplicación
from app.api import manipulate_datasets, pages, search, auth, contact, users
from app.db_core.connection import SessionLocal, get_db
from app.db_core.migraciones import aplicar_migraciones
from app.db_core.models import UsuarioModel
from app.nlp_model import generar_embedding_consulta, NOMBRE_MODELO
from app.db_chroma import coleccion, modelo_indexado, registrar_modelo_indexado
from app.limiter import limiter
from app.security import cifrar_password

# Configuración de logging para consola y archivo para auditoria
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(), # En desarrollo se puede usar LOG_LEVEL=DEBUG en el .env para ver el detalle de cada búsqueda
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/auditoria.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# --- CONTROL GLOBAL DE ESTADO (HEALTH PROBES) ---
app_state = {
    "warmup_ready": False,
    "modelo_compatible": False
}

# --- CICLO DE VIDA (STARTUP) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear o actualizar las tablas con Alembic (create_all no agregaba columnas nuevas a tablas existentes).
    # Con una sola réplica es seguro hacerlo al arrancar; con varias, conviene moverlo a un paso previo del despliegue.
    aplicar_migraciones()

    db = SessionLocal()
    try:
        admin_existente = db.query(UsuarioModel).first()
        if not admin_existente:
            user_env = os.getenv("ADMIN_USER")
            pass_env = os.getenv("ADMIN_PASSWORD")
            if not user_env or not pass_env:
                raise RuntimeError("ADMIN_USER y ADMIN_PASSWORD deben estar configuradas en el .env")

            nuevo_admin = UsuarioModel(
                username=user_env,
                password_hash=cifrar_password(pass_env),
                rol="admin"
            )
            db.add(nuevo_admin)
            db.commit()
            print("¡Administrador inicial registrado desde el .env!")
    finally:
        db.close()

    # --- COMPATIBILIDAD DEL ÍNDICE ---
    # Dos modelos pueden generar vectores del mismo tamaño: si el índice se creó con otro modelo, ChromaDB no falla,
    # pero compara vectores incompatibles y la búsqueda devuelve resultados sin sentido. En ese caso no se marca la app como lista.
    indexado_con = modelo_indexado()
    if coleccion.count() == 0 and indexado_con != NOMBRE_MODELO:
        registrar_modelo_indexado(NOMBRE_MODELO) # Colección vacía: todo lo que se agregue desde el panel usará el modelo actual
        indexado_con = NOMBRE_MODELO
    app_state["modelo_compatible"] = indexado_con == NOMBRE_MODELO
    if not app_state["modelo_compatible"]:
        logger.error(
            f"ChromaDB se indexó con '{indexado_con or 'un modelo anterior no registrado'}', pero la app usa '{NOMBRE_MODELO}'. "
            "Ejecuta scripts/migrate_chroma.py para re-indexar."
        )

    # --- WARM-UP ---
    try:
        vector_test = generar_embedding_consulta("warm up test municipal")
        coleccion.query(query_embeddings=[vector_test], n_results=1)
        app_state["warmup_ready"] = True
        print("[WARM-UP] Modelo semántico y ChromaDB precargados exitosamente en RAM.")
    except Exception as e:
        app_state["warmup_ready"] = False
        print(f"[WARM-UP] Aviso durante precarga del modelo: {e}")

    yield  # --- la app queda corriendo aquí ---

    # (nada que limpiar al apagar por ahora)


app = FastAPI(title="API Buscador Semántico Gubernamental", lifespan=lifespan)

# --- RATE LIMITING ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Servidores de archivos estáticos
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

# Registro modular de rutas
app.include_router(pages.router)
app.include_router(search.router)
app.include_router(manipulate_datasets.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(contact.router)

# Configuración de CORS
origenes_permitidos = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MIDDLEWARE DE SEGURIDAD HTTP ---

# Swagger (/docs) y ReDoc (/redoc) los genera FastAPI con un script inline y recursos de CDN.
# Solo en esas páginas se permite: muestran la documentación de la API, nunca contenido escrito por usuarios.
RUTAS_DOCUMENTACION_API = {"/docs", "/docs/oauth2-redirect", "/redoc"}
CSP_DOCUMENTACION_API = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "font-src 'self' https://fonts.gstatic.com; "
    "worker-src 'self' blob:; " # ReDoc procesa la especificación en un web worker
    "connect-src 'self';"
)

@app.middleware("http")
async def agregar_cabeceras_seguridad(request: Request, call_next):
    response = await call_next(request)
    
    # Cabeceras de protección contra ataques comunes
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Content-Security-Policy (CSP)
    if request.url.path in RUTAS_DOCUMENTACION_API:
        csp = CSP_DOCUMENTACION_API
    else:
        csp = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; " # Sin 'unsafe-inline': todo el JS vive en archivos .js, así un script inyectado no se ejecuta
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self';"
        )
    response.headers["Content-Security-Policy"] = csp
    
    return response

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
    que ChromaDB esté en RAM y que la base relacional responda consultas.
    """
    errores = []

    if not app_state["warmup_ready"]:
        errores.append("Warm-up del modelo semántico o ChromaDB en progreso.")

    if not app_state["modelo_compatible"]:
        errores.append("La base vectorial se indexó con otro modelo de embeddings; hay que re-indexarla.")

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness: la base de datos no respondió")
        errores.append("Base de datos no disponible.") # Este endpoint es público: el detalle del error solo va al log

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
            "db_relacional": "ok",
            "nlp_chromadb": "ok"
        }
    }