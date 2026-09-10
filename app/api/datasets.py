import os
import shutil
import uuid
import json
from datetime import datetime
import pandas as pd
import logging
import hashlib

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, logger, status, Depends
from fastapi.responses import FileResponse, Response

# Módulos internos del proyecto
from app.database import coleccion, guardar_datasets, obtener_todos_datasets
from app.nlp_model import generar_embedding
from app.api.auth import verificar_token

router = APIRouter(tags=["Gestión y Descarga de Datasets"])
logger = logging.getLogger(__name__)

@router.get("/api/admin/datasets")
def listar_datasets_admin():
    datos = obtener_todos_datasets()
    resultados = []
    
    if datos and datos.get("ids"):
        for i in range(len(datos["ids"])):
            meta = datos["metadatas"][i] if datos["metadatas"] else {}
            resultados.append({
                "id": datos["ids"][i],
                "titulo": datos["documents"][i],
                "dependencia": meta.get("dependencia", "No registrada"),
                "categoria": meta.get("categoria", "No registrada"),
                "fecha": meta.get("fecha_actualizacion", "N/A")
            })
            
    return {"resultados": resultados}

@router.post("/api/admin/subir")
async def publicar_dataset(
    titulo: str = Form(...),
    descripcion: str = Form(...),
    dependencia: str = Form(...),
    categoria: str = Form(...),
    archivo: UploadFile = File(...),
    usuario_autenticado: str = Depends(verificar_token)
):

    logger.info(f"[BITACORA AUDITORIA] El administrador '{usuario_autenticado}' subió el dataset '{titulo}' con el archivo '{archivo.filename}' a la dependencia '{dependencia}'.")

    if not archivo.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Solo se permiten archivos .csv"
        )
        
    if archivo.content_type not in ["text/csv", "application/vnd.ms-excel"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contenido del archivo no es un CSV válido."
        )

    contenido_archivo = await archivo.read()
    hash_calculado = hashlib.sha256(contenido_archivo).hexdigest()

    await archivo.seek(0)

    datos_existentes = obtener_todos_datasets()
    if datos_existentes and datos_existentes.get("metadatas"):
        for meta in datos_existentes["metadatas"]:
            # Validar que meta no sea None antes de buscar el hash
            if meta and meta.get("hash_sha256") == hash_calculado:
                logger.warning(f"[ALERTA] Ingesta bloqueada por duplicidad: {archivo.filename}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Este dataset ya fue subido anteriormente (Duplicado detectado)."
                )

    id_unico = str(uuid.uuid4())
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    carpeta_destino = "data/raw"
    os.makedirs(carpeta_destino, exist_ok=True) 
    ruta_archivo = f"{carpeta_destino}/{id_unico}.csv"
    
    with open(ruta_archivo, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)
        
    texto_completo = f"{titulo}. {descripcion} Dependencia: {dependencia}"
    vector = generar_embedding(texto_completo) 
    
    metadata = {
        "dependencia": dependencia,
        "categoria": categoria, 
        "descripcion": descripcion,
        "fecha_actualizacion": fecha_actual,
        "hash_sha256": hash_calculado
    }
    
    guardar_datasets(
        ids=[id_unico], 
        textos=[titulo], 
        embeddings=[vector],
        metadatas=[metadata]
    )
    
    logger.info(f"[EXITO] Dataset '{titulo}' subido exitosamente con ID: {id_unico}'.")
    return {
        "mensaje": "Dataset publicado exitosamente", 
        "id": id_unico,
        "archivo_guardado": archivo.filename
    }

@router.delete("/api/admin/datasets/{id_dataset}")
def eliminar_dataset(
    id_dataset: str, 
    usuario_autenticado: str = Depends(verificar_token)
    ):

    # Bitácora de auditoría
    logger.info(f"[BITACORA AUDITORIA] El administrador '{usuario_autenticado}' eliminó el dataset con ID: {id_dataset}")

    try:
        coleccion.delete(ids=[id_dataset])
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al limpiar la base de datos: {str(e)}"
        )

    ruta_csv = f"data/raw/{id_dataset}.csv"
    if os.path.exists(ruta_csv):
        os.remove(ruta_csv)
    
    return {"mensaje": "Dataset eliminado permanentemente"}

@router.get("/api/descargar/{id_dataset}")
def descargar_dataset(id_dataset: str, formato: str = "csv"):
    ruta_csv = f"data/raw/{id_dataset}.csv"
    
    if not os.path.exists(ruta_csv):
        raise HTTPException(status_code=404, detail="Dataset no encontrado")
        
    if formato == "csv":
        return FileResponse(path=ruta_csv, filename=f"{id_dataset}.csv", media_type="text/csv")
        
    try:
        df = pd.read_csv(ruta_csv, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(ruta_csv, encoding="latin-1")
    
    if formato == "json":
        json_data = df.to_json(orient="records")
        return Response(content=json_data, media_type="application/json", 
                        headers={"Content-Disposition": f"attachment; filename={id_dataset}.json"})
                        
    elif formato == "xml":
        df_xml = df.copy()
        df_xml.columns = df_xml.columns.str.replace(r'\W+', '_', regex=True)
        xml_data = df_xml.to_xml(index=False)
        return Response(content=xml_data, media_type="application/xml", 
                        headers={"Content-Disposition": f"attachment; filename={id_dataset}.xml"})
                        
    elif formato == "geojson":
        df.columns = df.columns.str.lower() # Estandariza a minúsculas
        features = []
        for _, row in df.iterrows():
            feature = {"type": "Feature", "properties": row.to_dict(), "geometry": None}
            lat = row.get("latitud") or row.get("lat")
            lon = row.get("longitud") or row.get("lon")

            try:

                lat_float = float(lat)
                lon_float = float(lon)
            
                if pd.notna(lat) and pd.notna(lon):
                    feature["geometry"] = {"type": "Point", "coordinates": [lon_float, lat_float]} 

            except (ValueError, TypeError):
                pass
                
            features.append(feature)
            
        geojson_data = {"type": "FeatureCollection", "features": features}
        return Response(content=json.dumps(geojson_data), media_type="application/geo+json", 
                        headers={"Content-Disposition": f"attachment; filename={id_dataset}.geojson"})
    
    raise HTTPException(status_code=400, detail="Formato no soportado")