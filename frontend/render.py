# Este script convierte las plantillas Jinja2 del frontend en HTML estático para que nginx las sirva.
# Las mismas plantillas las renderiza FastAPI en la imagen de Azure (api/app/api/pages.py), así que hay una sola fuente.
#
# Uso: python render.py <carpeta_salida>

import sys
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

CARPETA = Path(__file__).resolve().parent


def main():
    salida = Path(sys.argv[1])
    salida.mkdir(parents=True, exist_ok=True)
    entorno = Environment(loader=FileSystemLoader(CARPETA))

    for plantilla in sorted(CARPETA.glob("*.html")):
        if plantilla.name == "base.html": # Solo la heredan las demás páginas
            continue
        # base.html usa request.url.path para marcar la sección activa del menú
        ruta = "/" if plantilla.name == "index.html" else f"/{plantilla.name}"
        request = SimpleNamespace(url=SimpleNamespace(path=ruta))
        html = entorno.get_template(plantilla.name).render(request=request)
        (salida / plantilla.name).write_text(html, encoding="utf-8")
        print(f"{ruta} -> {plantilla.name}")


if __name__ == "__main__":
    main()
