# Este archivo mantiene la tabla relacional "datasets" alineada con ChromaDB, que es donde se indexa el catálogo

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.db_chroma import obtener_todos_datasets
from app.db_core.models import DatasetModel

logger = logging.getLogger(__name__)


def fecha_desde_texto(texto):
    # ChromaDB guarda la fecha como texto "AAAA-MM-DD"; un valor vacío o mal formado queda como "sin fecha"
    try:
        return date.fromisoformat(texto) if texto else None
    except (TypeError, ValueError):
        return None


def valores_desde_chroma(titulo: str, meta: dict) -> dict:
    meta = meta or {}
    return {
        "titulo": titulo,
        "descripcion": meta.get("descripcion", ""),
        "dependencia": meta.get("dependencia", ""),
        "categoria": meta.get("categoria", ""),
        "archivo_original": meta.get("archivo_original") or None,
        "hash_sha256": meta.get("hash_sha256") or None,
        "fecha_actualizacion": fecha_desde_texto(meta.get("fecha_actualizacion")),
    }


def sincronizar_datasets(db: Session):
    """
    Copia a la tabla datasets el catálogo que hay en ChromaDB: inserta los que faltan, actualiza los que cambiaron
    y borra los que ya no están (con sus descargas y reportes). Se llama al arrancar la app, después de las
    migraciones: en docker compose ChromaDB se llena con la semilla antes de iniciar la API, y en Azure la base
    relacional es efímera pero ChromaDB viene en la imagen.
    """
    datos = obtener_todos_datasets()
    existentes = {d.id: d for d in db.query(DatasetModel).all()}
    ids_chroma = set()
    nuevos = 0

    for id_dataset, titulo, meta in zip(datos.get("ids", []), datos.get("documents", []), datos.get("metadatas", [])):
        ids_chroma.add(id_dataset)
        valores = valores_desde_chroma(titulo, meta)
        fila = existentes.get(id_dataset)
        if fila:
            for campo, valor in valores.items():
                setattr(fila, campo, valor)
        else:
            db.add(DatasetModel(id=id_dataset, **valores))
            nuevos += 1

    retirados = [fila for id_dataset, fila in existentes.items() if id_dataset not in ids_chroma]
    for fila in retirados:
        db.delete(fila)

    db.commit()
    logger.info(f"Tabla datasets sincronizada con ChromaDB: {len(ids_chroma)} datasets ({nuevos} nuevos, {len(retirados)} retirados)")
