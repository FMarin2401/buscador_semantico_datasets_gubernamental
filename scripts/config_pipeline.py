# Configuracion compartida por los scripts del pipeline de ingesta:
#   1. analyze_csv.py    -> Gemini genera los metadatos y los guarda en CATALOGO_GEMINI
#   2. Revision humana   -> una persona revisa ese archivo y guarda la version final como CATALOGO_REVISADO
#   3. migrate_chroma.py -> indexa CATALOGO_REVISADO en ChromaDB y copia los CSV a data/raw
#
# El paso 2 es intencional: Gemini puede inventar una dependencia que suene oficial o una descripcion imprecisa.

CARPETA_ORIGINALES = "data/entregados_municipio/" # CSV tal como los entrega el municipio
CATALOGO_GEMINI = "data/clean/catalogo_maestro_procesado.csv" # Salida de Gemini, sin revisar
CATALOGO_REVISADO = "data/clean/catalogo_maestro.csv" # Version revisada; es la unica que se indexa
CARPETA_RAW_PRODUCCION = "data/raw/" # CSV que sirve la app, nombrados con el ID del dataset

# Categorias oficiales para los filtros del buscador. Gemini solo puede elegir una de estas.
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
