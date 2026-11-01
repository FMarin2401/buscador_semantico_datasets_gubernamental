# Este archivo define las categorias oficiales del catalogo.
# Es la unica fuente: la usan la API (validacion y GET /api/categorias), el panel de administracion
# y el pipeline de ingesta con Gemini (scripts/config_pipeline.py).

CATEGORIAS = [
    "Movilidad",
    "Medio Ambiente",
    "Seguridad",
    "Economía",
    "Infraestructura y Obras",
    "Salud",
    "Desarrollo Social",
    "Administración y Finanzas",
    "Cultura y Deporte",
    "Educación",
]
