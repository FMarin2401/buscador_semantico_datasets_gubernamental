import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

# Módulos internos del proyecto
from app.catalogo import CATEGORIAS
from app.limiter import limiter
from app.db_chroma import buscar_similares, coleccion
from app.nlp_model import generar_embedding_consulta, UMBRAL_DISTANCIA
from app.db_core.models import DescargasDatasetModel
from app.db_core.connection import get_db
from app.api.esquemas import ERROR_429

router = APIRouter(tags=["Búsqueda Semántica"])
logger = logging.getLogger(__name__)


class DatasetResultado(BaseModel):
    id: str = Field(description="UUID del dataset; se usa en /api/descargar/{id} y en la vista previa")
    dataset_recomendado: str = Field(description="Título del dataset")
    descripcion: str
    dependencia: str
    categoria: str
    fecha_actualizacion: Optional[str] = Field(description="AAAA-MM-DD, o null si no se registró")
    distancia: float = Field(description="Distancia coseno a la consulta (menor = más parecido). 0 en el catálogo completo")
    descargas: int


EJEMPLO_DATASET = {
    "id": "6d1c0f3a-8b52-5e1e-9c41-2f0a7a1b9e10",
    "dataset_recomendado": "Centros de Acopio de Neumáticos",
    "descripcion": "Lugares autorizados para la recolección de llantas usadas.",
    "dependencia": "Dirección General de Medio Ambiente",
    "categoria": "Medio Ambiente",
    "fecha_actualizacion": "2026-10-22",
    "distancia": 0.1312,
    "descargas": 4,
}


class ResultadosBusqueda(BaseModel):
    busqueda: str
    resultados: list[DatasetResultado]

    model_config = ConfigDict(json_schema_extra={"examples": [{"busqueda": "dónde tiro mis llantas viejas", "resultados": [EJEMPLO_DATASET]}]})


class Catalogo(BaseModel):
    resultados: list[DatasetResultado]

    model_config = ConfigDict(json_schema_extra={"examples": [{"resultados": [{**EJEMPLO_DATASET, "distancia": 0.0}]}]})


class ListaCategorias(BaseModel):
    categorias: list[str]

    model_config = ConfigDict(json_schema_extra={"examples": [{"categorias": ["Movilidad", "Medio Ambiente", "Seguridad"]}]})


def obtener_conteos_descargas(db: Session, ids: list) -> dict:
    # Solo se consultan los datasets que se van a devolver, no la tabla completa
    if not ids:
        return {}
    filas = db.query(DescargasDatasetModel.id_dataset, DescargasDatasetModel.total_descargas) \
        .filter(DescargasDatasetModel.id_dataset.in_(ids)).all()
    return dict(filas)


def formatear_dataset(id_dataset: str, titulo: str, meta: dict, distancia: float, descargas: int) -> dict:
    # Formato único de un resultado; lo comparten el catálogo completo y la búsqueda semántica
    meta = meta or {}
    return {
        "id": id_dataset,
        "dataset_recomendado": titulo,
        "descripcion": meta.get("descripcion", "Sin descripcion disponible"),
        "dependencia": meta.get("dependencia", "No registrada"),
        "categoria": meta.get("categoria", "General"),
        "fecha_actualizacion": meta.get("fecha_actualizacion"), # None si no hay fecha: el frontend muestra "Sin fecha"
        "distancia": round(distancia, 4),
        "descargas": descargas,
    }


@router.get(
    "/api/categorias",
    response_model=ListaCategorias,
    summary="Categorías oficiales",
    description="Las únicas categorías que acepta el catálogo. Las usan los filtros del portal y el formulario del panel.",
)
def listar_categorias():
    # Categorías oficiales, para los selectores del panel (una sola fuente: app/catalogo.py)
    return {"categorias": CATEGORIAS}


@router.get(
    "/api/catalogos",
    response_model=Catalogo,
    summary="Catálogo completo",
    description="Todos los datasets publicados con su número de descargas. El portal pagina y filtra en el navegador.",
)
def obtener_todo_el_catalogo(db: Session = Depends(get_db)):
    todos = coleccion.get(include=["documents", "metadatas"])
    ids = todos.get("ids", [])
    conteos = obtener_conteos_descargas(db, ids)

    catalogos_completos = [
        formatear_dataset(id_actual, documento, meta, 0.0, conteos.get(id_actual, 0)) # Si nunca se ha descargado, retorna 0
        for id_actual, documento, meta in zip(ids, todos.get("documents", []), todos.get("metadatas", []))
    ]
    return {"resultados": catalogos_completos}

@router.get(
    "/api/buscar",
    response_model=ResultadosBusqueda,
    summary="Búsqueda semántica",
    description=(
        "Convierte la consulta en un embedding (modelo `intfloat/multilingual-e5-small`) y devuelve hasta 10 datasets "
        "parecidos en significado, aunque no compartan palabras. Descarta los que superan el umbral de distancia, así que "
        "una consulta sin relación con el catálogo devuelve una lista vacía. Límite: 15 búsquedas por minuto por IP."
    ),
    responses={429: ERROR_429},
)
@limiter.limit("15/minute")
def buscar_dataset(
    request: Request,
    prompt: str = Query(..., min_length=2, max_length=300, description="Consulta en lenguaje natural", examples=["dónde tiro mis llantas viejas"]), # Evita textos enormes que solo gastan CPU al generar el embedding
    db: Session = Depends(get_db)
):
    vector_prompt = generar_embedding_consulta(prompt)

    n_meta = 10
    resultados = buscar_similares(vector_prompt, n_resultados=n_meta)

    logger.debug("--- INICIO DE BÚSQUEDA ---")
    logger.debug(f"Prompt del usuario: {prompt}")

    documents = resultados.get('documents', [[]])[0]
    distances = resultados.get('distances', [[]])[0]
    metadatas = resultados.get('metadatas', [[]])[0]
    ids = resultados.get('ids', [[]])[0]

    for idx, (doc, dist) in enumerate(zip(documents, distances)):
        logger.debug(f"Top {idx + 1}: {doc} | Distancia: {dist}")
    logger.debug("------------------\n")

    umbral_maximo = UMBRAL_DISTANCIA # Depende del modelo de embeddings; se calibra con scripts/evaluate_model.py
    validos = [
        (id_actual, documento, meta, distancia)
        for id_actual, documento, meta, distancia in zip(ids, documents, metadatas, distances)
        if distancia <= umbral_maximo
    ]

    conteos = obtener_conteos_descargas(db, [id_actual for id_actual, _, _, _ in validos])
    resultados_validos = [
        formatear_dataset(id_actual, documento, meta, distancia, conteos.get(id_actual, 0))
        for id_actual, documento, meta, distancia in validos
    ]

    return {"busqueda": prompt, "resultados": resultados_validos}
