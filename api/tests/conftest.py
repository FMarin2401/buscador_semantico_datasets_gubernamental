# Configuración compartida de las pruebas.
#
# Cada corrida trabaja en una carpeta temporal con su propia SQLite, ChromaDB, data/raw y logs, así que nunca toca
# los datos de desarrollo ni los del contenedor. Usa el modelo de embeddings real (viene en la imagen de Docker),
# porque las pruebas de búsqueda dependen de él.
#
# Uso:  docker compose exec api pytest        (o, sin Docker, desde api/:  pytest)

import atexit
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

RAIZ_API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_API))

os.environ.pop("DATABASE_URL", None) # En el contenedor apunta a PostgreSQL; las pruebas usan una SQLite temporal
os.environ.update(
    SECRET_KEY="clave-solo-para-pruebas-con-al-menos-32-bytes",
    ADMIN_USER="admin_pruebas",
    ADMIN_PASSWORD="Admin_Pruebas_2026",
    ENVIRONMENT="local",
)

EDITOR = {"username": "editor_pruebas", "password": "Editor_Pruebas_2026", "rol": "editor"}


@pytest.fixture(scope="session")
def cliente():
    # Antes de importar la app: ChromaDB, SQLite, data/raw y logs usan rutas relativas a la carpeta de trabajo.
    # Se cambia aquí y no al cargar este archivo, para no alterar la carpeta donde pytest busca las pruebas
    carpeta = tempfile.mkdtemp(prefix="pruebas_buscador_")
    os.chdir(carpeta)
    atexit.register(shutil.rmtree, carpeta, ignore_errors=True)

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c: # Ejecuta el lifespan: migraciones, administrador inicial y carga del modelo
        yield c


@pytest.fixture(autouse=True)
def reiniciar_limites():
    # Cada prueba empieza sin peticiones contadas; las que prueban el 429 hacen sus propias peticiones
    from app.limiter import limiter
    limiter.reset()


@pytest.fixture(scope="session")
def tokens(cliente):
    """Inicia sesión una vez como administrador y como editor, y guarda sus cookies."""
    def iniciar_sesion(usuario, password):
        cliente.cookies.clear()
        r = cliente.post("/api/login", json={"usuario": usuario, "password": password})
        assert r.status_code == 200, r.text
        return r.cookies["access_token"]

    admin = iniciar_sesion(os.environ["ADMIN_USER"], os.environ["ADMIN_PASSWORD"])
    cliente.cookies.set("access_token", admin)
    assert cliente.post("/api/admin/usuarios", json=EDITOR).status_code == 201
    editor = iniciar_sesion(EDITOR["username"], EDITOR["password"])
    cliente.cookies.clear()
    return {"admin": admin, "editor": editor}


def _con_sesion(cliente, token):
    cliente.cookies.clear()
    if token:
        cliente.cookies.set("access_token", token)
    return cliente


@pytest.fixture
def como_admin(cliente, tokens):
    yield _con_sesion(cliente, tokens["admin"])
    cliente.cookies.clear()


@pytest.fixture
def como_editor(cliente, tokens):
    yield _con_sesion(cliente, tokens["editor"])
    cliente.cookies.clear()


@pytest.fixture
def sin_sesion(cliente):
    return _con_sesion(cliente, None)


def csv_unico(filas: int = 3) -> bytes:
    """CSV con un identificador aleatorio: cada llamada produce un archivo distinto (otro hash SHA-256)."""
    marca = uuid.uuid4().hex[:8]
    lineas = ["folio,colonia,latitud,longitud"] + [f"{marca}-{i},Centro,21.12{i},-101.68{i}" for i in range(filas)]
    return ("\n".join(lineas) + "\n").encode()


def publicar(cliente, titulo="Dataset de prueba", descripcion="Descripción de un dataset de prueba.",
             dependencia="Dirección de Pruebas", categoria="Movilidad", contenido=None, nombre="datos.csv"):
    """Publica un dataset (con la sesión que tenga el cliente) y devuelve la respuesta."""
    return cliente.post(
        "/api/admin/subir",
        data={"titulo": titulo, "descripcion": descripcion, "dependencia": dependencia, "categoria": categoria},
        files={"archivo": (nombre, contenido if contenido is not None else csv_unico(), "text/csv")},
    )


@pytest.fixture
def sesion(cliente, tokens):
    """Cambia de rol a mitad de una prueba: sesion("admin"), sesion("editor") o sesion(None)."""
    yield lambda rol: _con_sesion(cliente, tokens[rol] if rol else None)
    cliente.cookies.clear()


@pytest.fixture
def dataset(cliente, tokens):
    """Un dataset recién publicado; devuelve su ID. Cada prueba recibe uno nuevo."""
    previa = cliente.cookies.get("access_token") # La sesión que haya puesto otro fixture (como_admin, como_editor...)
    r = publicar(_con_sesion(cliente, tokens["admin"]), titulo=f"Dataset {uuid.uuid4().hex[:6]}")
    assert r.status_code == 201, r.text
    _con_sesion(cliente, previa)
    return r.json()["id"]
