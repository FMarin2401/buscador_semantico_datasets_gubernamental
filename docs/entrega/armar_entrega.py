# Arma la carpeta de entrega del 2.º parcial con la estructura que pide la rúbrica (secciones 00 a 08).
#
# El código (04_Codigo) sale de "git archive": solo lo versionado en el último commit. Así nunca se copian el .env real,
# api/data (con la base de usuarios), api/logs, env/ ni __pycache__, aunque existan en la carpeta de trabajo.
#
# Uso (desde la raíz del repositorio, con la app levantada para exportar openapi.json):
#   docker compose up -d
#   python3 docs/entrega/armar_entrega.py
#   python3 docs/entrega/armar_entrega.py --destino /mnt/c/Users/<usuario>/OneDrive/...   # Directo a OneDrive
#
# Las capturas van en docs/entrega/07_Evidencias/ y la presentación en docs/entrega/08_Presentacion/:
# se copian tal cual si existen.

import argparse
import io
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ENTREGA = RAIZ / "docs" / "entrega"

MATRICULA = "192405-1"
NOMBRE_COMPLETO = "Francisco Marín Castillo"
NOMBRE_CARPETA = f"{MATRICULA}_MarinCastillo_Francisco_2P"
PROYECTO = "Buscador Semántico de Datasets Gubernamentales (Portal de Datos Abiertos de León)"
REPOSITORIO = "https://github.com/FMarin2401/buscador_semantico_datasets_gubernamental"

PROHIBIDOS = {".env", "node_modules", "venv", "env", "__pycache__", ".git"}
EXTENSIONES_PROHIBIDAS = {".db", ".sqlite3", ".pyc", ".log"}

CAPTURAS_SUGERIDAS = """# Evidencias pendientes

Coloca aquí tus capturas (PNG) y vuelve a ejecutar `armar_entrega.py`. La rúbrica pide como mínimo:

- [ ] `/docs` de Swagger con la lista de endpoints (y uno abierto con sus ejemplos y códigos)
- [ ] Prueba negativa: `PATCH /api/admin/reportes/{id}` a un reporte resuelto con `{"estado": "abierto"}` → `409`
- [ ] Estado vacío: búsqueda sin resultados en Explorar Datos, o la bandeja de reportes vacía
- [ ] Estado de error: por ejemplo, el formulario de reporte con un error de validación
- [ ] Salida de `docker compose exec api pytest` (60 passed)
- [ ] `docker compose ps` con los tres contenedores sanos
- [ ] SC-001: reporte enviado desde la ficha (con su folio) y atendido en el panel

Regla 6: lo que afirma la IA no cuenta como evidencia; estas capturas deben ser tuyas.
"""


def ejecutar(*comando, **opciones):
    return subprocess.run(comando, cwd=RAIZ, check=True, capture_output=True, **opciones)


def copiar(origen: Path, destino: Path):
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino / origen.name)


def copiar_carpeta_si_existe(origen: Path, destino: Path) -> int:
    destino.mkdir(parents=True, exist_ok=True)
    archivos = [a for a in origen.glob("*") if a.is_file()] if origen.exists() else []
    for archivo in archivos:
        shutil.copy2(archivo, destino / archivo.name)
    return len(archivos)


def exportar_openapi(url: str) -> dict:
    """La especificación de la app en ejecución; si no responde, la genera dentro del contenedor de la API."""
    try:
        with urllib.request.urlopen(url, timeout=10) as respuesta:
            return json.load(respuesta)
    except OSError:
        print(f"  {url} no respondió; genero openapi.json dentro del contenedor api")
    try:
        salida = ejecutar("docker", "compose", "exec", "-T", "api", "python", "-c",
                          "import json; from app.main import app; print(json.dumps(app.openapi()))", text=True)
        return json.loads(salida.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        sys.exit("ERROR: no pude obtener openapi.json. Levanta la app con 'docker compose up -d' y vuelve a intentar.")


def extraer_codigo(destino: Path) -> str:
    commit = ejecutar("git", "rev-parse", "--short", "HEAD", text=True).stdout.strip()
    archivo = ejecutar("git", "archive", "--format=tar", "HEAD").stdout
    destino.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archivo)) as tar:
        tar.extractall(destino, filter="data")
    return commit


def archivos(n: int) -> str:
    return f"{n} archivo" if n == 1 else f"{n} archivos"


def leeme(commit: str, n_evidencias: int, n_presentacion: int) -> str:
    return f"""# {NOMBRE_COMPLETO} · 2.º Parcial de Ingeniería de Software

| | |
|---|---|
| **Nombre** | {NOMBRE_COMPLETO} |
| **Matrícula** | {MATRICULA} |
| **Proyecto** | {PROYECTO} |
| **Repositorio** | {REPOSITORIO} (commit `{commit}`) |
| **Aplicación local** | http://localhost:8080 · Swagger: http://localhost:8080/docs |
| **Demo pública (Azure)** | https://buscador.frankmarincas.dev (misma versión, en un solo contenedor con SQLite por ser cuenta de estudiante; la entrega evaluable es la de `04_Codigo`) |

Plataforma de datos abiertos del Municipio de León con **búsqueda semántica**: el ciudadano escribe con sus propias palabras ("dónde tiro mis llantas viejas") y el sistema encuentra el dataset por significado. Incluye descarga en CSV/JSON/XML/GeoJSON, buzón ciudadano, reportes de problemas en datasets (SC-001) y un panel de administración con roles.

## Cómo ejecutarlo

Requisito: Docker Desktop abierto. Dentro de `04_Codigo/`:

```bash
cp .env.example .env
docker compose up --build
```

Detalles, cómo detener y problemas comunes: `04_Codigo/README.md`.

## Contenido

| Carpeta | Contenido | Criterio |
|---|---|---|
| `01_Arquitectura/` | `C4_Contexto` y `DAR_Arquitectura` (.drawio + .png) | A1, A2 |
| `02_Datos/` | `DER` (.drawio + .png), `DDA.md` (diccionario de datos) y `objetos_bd.sql` (índice y vista con su justificación) | A3, A4 |
| `03_API/` | `Diseno_API.md` (endpoints, códigos de respuesta, reglas de negocio y seguridad) y `openapi.json` exportado de la app | A5, B4 |
| `04_Codigo/` | Proyecto completo: `frontend/` (nginx), `api/` (FastAPI, pruebas en `api/tests/`), `db/` (datos de ejemplo y objetos de BD), `docker-compose.yml`, `.env.example`, `CLAUDE.md` y `README.md` | B1–B5, C2 |
| `05_Cambios/` | `solicitudes_cambio.md`: SC-001, reportar problemas en un dataset | B6 |
| `06_IA/` | `bitacora_prompts.md`: 3 prompts clave y qué se ajustó en cada uno | C3 |
| `07_Evidencias/` | Capturas: contenedores, Swagger, búsqueda, estados vacío y de error, SC-001 y pruebas; la salida de pytest incluye las pruebas negativas (409, 422, 429) ({archivos(n_evidencias)}) | B2–B6 |
| `08_Presentacion/` | Presentación en vivo y guion de la demo ({archivos(n_presentacion)}) | D |

## Dónde ver cada requisito en la aplicación

| Requisito | Dónde |
|---|---|
| Tres contenedores separados | `docker compose ps`: `frontend` (nginx), `api` (FastAPI), `db` (PostgreSQL 16) |
| API REST con CRUD | Datasets y reportes: crear, consultar, actualizar y eliminar (`/docs`) |
| Prueba negativa | Reabrir un reporte resuelto → `409`. Automatizada en `api/tests/test_reportes.py`; correr con `docker compose exec api pytest` |
| SC-001 | Ficha de un dataset en *Explorar Datos* → «Reportar un problema»; panel → «Reportes de Datasets» |
| Índice y vista | `02_Datos/objetos_bd.sql`; la vista alimenta la tabla «Datasets con reportes» del panel |
"""


def verificar(carpeta: Path):
    problemas = [
        str(p.relative_to(carpeta)) for p in carpeta.rglob("*")
        if p.name in PROHIBIDOS or p.suffix in EXTENSIONES_PROHIBIDAS
    ]
    if problemas:
        sys.exit(f"ERROR: la entrega contiene archivos que no deben subirse: {problemas}")


def main():
    parser = argparse.ArgumentParser(description="Arma la carpeta de entrega del 2.º parcial.")
    parser.add_argument("--destino", type=Path, default=RAIZ / "salida_entrega", help="Carpeta donde se crea la entrega")
    parser.add_argument("--openapi-url", default="http://localhost:8080/openapi.json")
    args = parser.parse_args()

    pendientes = ejecutar("git", "status", "--porcelain", "--untracked-files=no", text=True).stdout.strip()
    if pendientes:
        print("AVISO: hay cambios sin commit; 04_Codigo se arma con el último commit y no los incluye:\n" + pendientes)

    salida = args.destino / NOMBRE_CARPETA
    if salida.exists():
        shutil.rmtree(salida)
    print(f"Armando {salida}")

    for archivo in (ENTREGA / "01_Arquitectura").glob("*"):
        copiar(archivo, salida / "01_Arquitectura")
    for archivo in list((ENTREGA / "02_Datos").glob("*")) + [RAIZ / "db" / "objetos_bd.sql"]:
        copiar(archivo, salida / "02_Datos")
    copiar(ENTREGA / "03_API" / "Diseno_API.md", salida / "03_API")
    especificacion = exportar_openapi(args.openapi_url)
    (salida / "03_API" / "openapi.json").write_text(json.dumps(especificacion, ensure_ascii=False, indent=2), encoding="utf-8")
    commit = extraer_codigo(salida / "04_Codigo")
    copiar(RAIZ / "docs" / "solicitudes_cambio.md", salida / "05_Cambios")
    copiar(ENTREGA / "06_IA" / "bitacora_prompts.md", salida / "06_IA")

    n_evidencias = copiar_carpeta_si_existe(ENTREGA / "07_Evidencias", salida / "07_Evidencias")
    if n_evidencias == 0:
        (salida / "07_Evidencias" / "PENDIENTE_capturas.md").write_text(CAPTURAS_SUGERIDAS, encoding="utf-8")
    n_presentacion = copiar_carpeta_si_existe(ENTREGA / "08_Presentacion", salida / "08_Presentacion")

    (salida / "00_LEEME.md").write_text(leeme(commit, n_evidencias, n_presentacion), encoding="utf-8")
    verificar(salida)

    print(f"Listo (código del commit {commit}, {len(especificacion['paths'])} rutas en openapi.json)")
    for seccion in sorted(salida.iterdir()):
        cantidad = sum(1 for p in seccion.rglob("*") if p.is_file()) if seccion.is_dir() else 1
        print(f"  {seccion.name:<20} {cantidad} archivo(s)")
    if n_evidencias == 0:
        print("  PENDIENTE: 07_Evidencias está vacía (ver PENDIENTE_capturas.md)")
    if n_presentacion == 0:
        print("  PENDIENTE: 08_Presentacion está vacía")


if __name__ == "__main__":
    main()
