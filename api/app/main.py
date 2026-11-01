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
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional

# Módulos internos de la aplicación
from app.api import manipulate_datasets, pages, search, auth, contact, users, reportes
from app.db_core.connection import SessionLocal, get_db
from app.db_core.migraciones import aplicar_migraciones
from app.db_core.sincronizacion import sincronizar_datasets
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

        # Descargas y reportes tienen llave foránea a la tabla datasets: debe tener el mismo catálogo que ChromaDB
        sincronizar_datasets(db)
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


DESCRIPCION_API = """
API del Portal de Datos Abiertos del Municipio de León: búsqueda semántica de datasets, descarga en varios formatos,
buzón ciudadano, reportes de problemas (SC-001) y administración del catálogo.

**Cómo probar los endpoints protegidos desde esta página:** ejecuta primero `POST /api/login` (con los valores de
`.env.example`: `admin_leon` / `Admin_Leon_2026`). El navegador guarda la cookie de sesión y la envía en las pruebas
siguientes. Los endpoints con candado la requieren; algunos además exigen rol de administrador (403 si no lo es).

**Seguridad:** JWT en cookie HttpOnly (30 min), contraseñas con Argon2, validación de entradas con Pydantic (422),
límite de peticiones por IP (429), CORS restringido a `ALLOWED_ORIGINS` y cabeceras de seguridad (CSP, HSTS).
"""

GRUPOS_API = [
    {"name": "Búsqueda Semántica", "description": "Consulta del catálogo en lenguaje natural. Público."},
    {"name": "Gestión y Descarga de Datasets", "description": "Descarga y vista previa (públicas); alta, edición, baja y bitácora (panel)."},
    {"name": "Reportes de datasets (SC-001)", "description": "Los ciudadanos reportan problemas en un dataset y el equipo los atiende. Ver docs/solicitudes_cambio.md."},
    {"name": "Contacto", "description": "Buzón ciudadano."},
    {"name": "Autenticación", "description": "Inicio y cierre de sesión."},
    {"name": "Administración de Usuarios", "description": "Funcionarios con acceso al panel. Solo administradores."},
    {"name": "Monitoreo", "description": "Estado del servicio para Docker y Azure (health checks)."},
]

app = FastAPI(
    title="API Buscador Semántico Gubernamental",
    description=DESCRIPCION_API,
    version="2.0.0",
    openapi_tags=GRUPOS_API,
    lifespan=lifespan,
)

# --- RATE LIMITING ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Servidores de archivos estáticos y páginas, solo si esta imagen incluye el frontend (ver pages.FRONTEND_DIR)
if pages.FRONTEND_DIR:
    app.mount("/css", StaticFiles(directory=f"{pages.FRONTEND_DIR}/css"), name="css")
    app.mount("/js", StaticFiles(directory=f"{pages.FRONTEND_DIR}/js"), name="js")
    app.mount("/assets", StaticFiles(directory=f"{pages.FRONTEND_DIR}/assets"), name="assets")
    app.include_router(pages.router)

# Registro modular de rutas
app.include_router(search.router)
app.include_router(manipulate_datasets.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(contact.router)
app.include_router(reportes.router)

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
            # Sin 'unsafe-inline': todo el JS vive en archivos .js, así un script inyectado no se ejecuta.
            # Del CDN solo se permite la versión fija de Chart.js que usa admin.html, no cualquier paquete de jsDelivr.
            "script-src 'self' https://cdn.jsdelivr.net/npm/chart.js@4.5.1/; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self';"
        )
    response.headers["Content-Security-Policy"] = csp
    
    return response

# --- ENDPOINTS DE MONITOREO Y HEALTH CHECKS ---

class EstadoServidor(BaseModel):
    mensaje: str = Field(examples=["Servidor en línea."])


class EstadoVida(BaseModel):
    status: Literal["alive"]


class Componentes(BaseModel):
    db_relacional: Literal["ok", "error"]
    nlp_chromadb: Literal["ok", "cargando"]
    indice_vectorial: Literal["ok", "incompatible"]


class EstadoListo(BaseModel):
    status: Literal["ready", "unhealthy"]
    ready: bool
    components: Componentes
    modelo: str = Field(description="Modelo de embeddings que usa la app")
    errores: Optional[list[str]] = Field(default=None, description="Solo cuando ready es false")

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "status": "ready",
        "ready": True,
        "components": {"db_relacional": "ok", "nlp_chromadb": "ok", "indice_vectorial": "ok"},
        "modelo": "intfloat/multilingual-e5-small",
    }]})


@app.get("/api/status", tags=["Monitoreo"], response_model=EstadoServidor, summary="Servidor en línea",
         description="Responde mientras el proceso atiende peticiones.")
def status_check():
    return {"mensaje": "Servidor en línea."}

@app.get("/api/health/live", tags=["Monitoreo"], response_model=EstadoVida, summary="Liveness probe",
         description="El proceso está vivo. Si deja de responder, Docker o Azure reinician el contenedor.")
def liveness_check():
    return {"status": "alive"}

@app.get(
    "/api/health/ready",
    tags=["Monitoreo"],
    response_model=EstadoListo,
    response_model_exclude_none=True,
    summary="Readiness probe",
    description=(
        "La app está lista para recibir tráfico: terminó la carga del modelo y de ChromaDB, el índice se generó con el "
        "mismo modelo que usa la app y la base relacional responde. Devuelve el estado de cada componente siempre; el "
        "healthcheck de docker compose y el panel de administración lo usan."
    ),
    responses={503: {"model": EstadoListo, "description": "Algún componente no está listo (mismo formato, con `errores`)"}},
)
def readiness_check(response: Response, db: Session = Depends(get_db)):
    errores = []
    # Estado por componente, siempre presente (también con 503): el panel de administración lo muestra tal cual
    componentes = {
        "db_relacional": "ok",
        "nlp_chromadb": "ok" if app_state["warmup_ready"] else "cargando",
        "indice_vectorial": "ok" if app_state["modelo_compatible"] else "incompatible",
    }

    if not app_state["warmup_ready"]:
        errores.append("Warm-up del modelo semántico o ChromaDB en progreso.")

    if not app_state["modelo_compatible"]:
        errores.append("La base vectorial se indexó con otro modelo de embeddings; hay que re-indexarla.")

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness: la base de datos no respondió")
        componentes["db_relacional"] = "error"
        errores.append("Base de datos no disponible.") # Este endpoint es público: el detalle del error solo va al log

    respuesta = {
        "status": "unhealthy" if errores else "ready",
        "ready": not errores,
        "components": componentes,
        "modelo": NOMBRE_MODELO,
    }
    if errores:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        respuesta["errores"] = errores
    return respuesta