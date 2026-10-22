import logging
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

# Módulos internos del proyecto
from app.limiter import limiter
from app.db_chroma import buscar_similares, coleccion
from app.nlp_model import generar_embedding_consulta, UMBRAL_DISTANCIA
from app.db_core.models import DescargasDatasetModel
from app.db_core.connection import get_db

router = APIRouter(tags=["Búsqueda Semántica"])
logger = logging.getLogger(__name__)


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


@router.get("/api/catalogos")
def obtener_todo_el_catalogo(db: Session = Depends(get_db)):
    todos = coleccion.get(include=["documents", "metadatas"])
    ids = todos.get("ids", [])
    conteos = obtener_conteos_descargas(db, ids)

    catalogos_completos = [
        formatear_dataset(id_actual, documento, meta, 0.0, conteos.get(id_actual, 0)) # Si nunca se ha descargado, retorna 0
        for id_actual, documento, meta in zip(ids, todos.get("documents", []), todos.get("metadatas", []))
    ]
    return {"resultados": catalogos_completos}

@router.get("/api/buscar")
@limiter.limit("15/minute")
def buscar_dataset(
    request: Request,
    prompt: str = Query(..., min_length=2, max_length=300), # Evita textos enormes que solo gastan CPU al generar el embedding
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
