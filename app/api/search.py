import logging
from fastapi import APIRouter

# Módulos internos del proyecto
from app.database import buscar_similares, coleccion
from app.nlp_model import generar_embedding

router = APIRouter(tags=["Búsqueda Semántica"])
logger = logging.getLogger(__name__)

@router.get("/api/catalogos") 
def obtener_todo_el_catalogo():
    todos = coleccion.get(include=["documents", "metadatas"]) 
    
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
            fecha_act = meta.get("fecha_actualizacion", "2026-01-01")
            descripcion = meta.get("descripcion", "Sin descripcion disponible") 
            
            catalogos_completos.append({
                "id": id_actual, 
                "dataset_recomendado": documento,
                "descripcion": descripcion,
                "dependencia": dependencia,
                "fecha_actualizacion": fecha_act,
                "distancia": 0.0 
            })
            
    return {"resultados": catalogos_completos}

@router.get("/api/buscar") 
def buscar_dataset(prompt: str):
    vector_prompt = generar_embedding(prompt) 
    
    n_meta = 15
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
    
    umbral_maximo = 0.60 

    resultados_validos = [] 
    
    for i in range(len(distances)): 
        distancia = distances[i] 
        
        if distancia <= umbral_maximo: 
            documento = documents[i]

            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            dependencia = meta.get('dependencia', "No registrada") 
            fecha_act = meta.get("fecha_actualizacion", "2026-01-01") 
            descripcion = meta.get("descripcion", "Sin descripcion disponible")
            
            resultados_validos.append({ 
                "id": ids[i] if i < len(ids) else "",
                "dataset_recomendado": documento,
                "descripcion": descripcion,
                "dependencia": dependencia,
                "fecha_actualizacion": fecha_act,
                "distancia": round(distancia, 4)
            })

    return {"busqueda": prompt, "resultados": resultados_validos}