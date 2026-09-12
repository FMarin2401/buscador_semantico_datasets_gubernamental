import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# Módulos internos del proyecto
from app.db_chroma import buscar_similares, coleccion
from app.nlp_model import generar_embedding
from app.db_users.models import DescargasDatasetModel
from app.db_users.connection import get_db

router = APIRouter(tags=["Búsqueda Semántica"])
logger = logging.getLogger(__name__)

@router.get("/api/catalogos") 
def obtener_todo_el_catalogo(db: Session = Depends(get_db)):
    todos = coleccion.get(include=["documents", "metadatas"]) 
    
    # 1. Consultar todos los conteos de descarga en SQLite
    conteos = dict(db.query(DescargasDatasetModel.id_dataset, DescargasDatasetModel.total_descargas).all())

    catalogos_completos = [] 
    if todos and "documents" in todos: 
        documents = todos["documents"]
        metadatas = todos.get("metadatas", [])
        ids = todos.get("ids", []) 
        
        for i in range(len(documents)): 
            documento = documents[i]
            id_actual = ids[i] if i < len(ids) else "" 

            meta = metadatas[i] if metadatas and i < len(metadatas) and metadatas[i] else {}
            dependencia = meta.get("dependencia", "No registrada")
            categoria = meta.get("categoria", "General")
            fecha_act = meta.get("fecha_actualizacion", "2026-01-01")
            descripcion = meta.get("descripcion", "Sin descripcion disponible") 
            
            catalogos_completos.append({
                "id": id_actual, 
                "dataset_recomendado": documento,
                "descripcion": descripcion,
                "dependencia": dependencia,
                "categoria": categoria,
                "fecha_actualizacion": fecha_act,
                "distancia": 0.0,
                "descargas": conteos.get(id_actual, 0) # Si nunca se ha descargado, retorna 0
            })
            
    return {"resultados": catalogos_completos}

@router.get("/api/buscar") 
def buscar_dataset(prompt: str, db: Session = Depends(get_db)):
    vector_prompt = generar_embedding(prompt) 
    
    n_meta = 10
    resultados = buscar_similares(vector_prompt, n_resultados=n_meta) 
    
    conteos = dict(db.query(DescargasDatasetModel.id_dataset, DescargasDatasetModel.total_descargas).all())

    logger.debug("--- INICIO DE BÚSQUEDA ---") 
    logger.debug(f"Prompt del usuario: {prompt}")
    
    documents = resultados.get('documents', [[]])[0] 
    distances = resultados.get('distances', [[]])[0] 
    metadatas = resultados.get('metadatas', [[]])[0] 
    ids = resultados.get('ids', [[]])[0] 
    
    for idx, (doc, dist) in enumerate(zip(documents, distances)): 
        logger.debug(f"Top {idx + 1}: {doc} | Distancia: {dist}")
    logger.debug("------------------\n")
    
    umbral_maximo = 0.60 
    resultados_validos = [] 
    
    for i in range(len(distances)): 
        distancia = distances[i] 
        
        if distancia <= umbral_maximo: 
            documento = documents[i]
            id_actual = ids[i] if i < len(ids) else ""

            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            dependencia = meta.get('dependencia', "No registrada")
            categoria = meta.get('categoria', "General")
            fecha_act = meta.get("fecha_actualizacion", "2026-01-01") 
            descripcion = meta.get("descripcion", "Sin descripcion disponible")
            
            resultados_validos.append({ 
                "id": id_actual,
                "dataset_recomendado": documento,
                "descripcion": descripcion,
                "dependencia": dependencia,
                "categoria": categoria,
                "fecha_actualizacion": fecha_act,
                "distancia": round(distancia, 4),
                "descargas": conteos.get(id_actual, 0) # Si nunca se ha descargado, retorna 0
            })

    return {"busqueda": prompt, "resultados": resultados_validos}