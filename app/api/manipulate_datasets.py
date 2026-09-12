import os
import shutil
import uuid
import json
from datetime import datetime
import pandas as pd
import logging
import hashlib

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status, Depends
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Módulos internos del proyecto
from app.db_chroma import coleccion, guardar_datasets, obtener_todos_datasets
from app.nlp_model import generar_embedding
from app.api.auth import verificar_token
from app.db_users.connection import get_db
from app.db_users.models import BitacoraAuditoriaModel

router = APIRouter(tags=["Gestión y Descarga de Datasets"])
logger = logging.getLogger(__name__)

class DatasetActualizar(BaseModel):
    titulo: str
    descripcion: str
    dependencia: str
    categoria: str

def registrar_evento_auditoria(db: Session, usuario: str, accion: str, detalles: str):
    """Inserta de manera transaccional un registro en la tabla de bitácora relacional."""
    nuevo_log = BitacoraAuditoriaModel(
        usuario=usuario,
        accion=accion,
        detalles=detalles
    )
    db.add(nuevo_log)
    db.commit()

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

@router.get("/api/admin/bitacora")
def obtener_bitacora(
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    """Devuelve los últimos 15 eventos registrados para el panel de auditoría."""
    logs = db.query(BitacoraAuditoriaModel).order_by(BitacoraAuditoriaModel.fecha_hora.desc()).limit(15).all()
    return {"registros": logs}

@router.post("/api/admin/subir")
async def publicar_dataset(
    titulo: str = Form(...),
    descripcion: str = Form(...),
    dependencia: str = Form(...),
    categoria: str = Form(...),
    archivo: UploadFile = File(...),
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
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
    
    # Registro dual: archivo plano y tabla de SQLite
    logger.info(f"[BITACORA AUDITORIA] El administrador '{usuario_autenticado}' subió el dataset '{titulo}' con ID: {id_unico}.")
    registrar_evento_auditoria(db, usuario_autenticado, "Publicación", f"{titulo} ({dependencia})")

    return {
        "mensaje": "Dataset publicado exitosamente", 
        "id": id_unico,
        "archivo_guardado": archivo.filename
    }

@router.put("/api/admin/datasets/{id_dataset}")
def actualizar_dataset(
    id_dataset: str, 
    datos: DatasetActualizar,
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    try:
        item_actual = coleccion.get(ids=[id_dataset], include=["metadatas", "documents"])
        if not item_actual or not item_actual.get("ids"):
            raise HTTPException(status_code=404, detail="Dataset no encontrado en la base de datos.")

        meta_vieja = item_actual["metadatas"][0] if item_actual["metadatas"] else {}
        hash_original = meta_vieja.get("hash_sha256", "")
        fecha_actual = datetime.now().strftime("%Y-%m-%d")

        nuevo_metadata = {
            "dependencia": datos.dependencia,
            "categoria": datos.categoria,
            "descripcion": datos.descripcion,
            "fecha_actualizacion": fecha_actual,
            "hash_sha256": hash_original
        }

        texto_completo = f"{datos.titulo}. {datos.descripcion} Dependencia: {datos.dependencia}"
        nuevo_vector = generar_embedding(texto_completo)

        coleccion.update(
            ids=[id_dataset],
            documents=[datos.titulo],
            embeddings=[nuevo_vector],
            metadatas=[nuevo_metadata]
        )

        logger.info(f"[BITACORA AUDITORIA] El administrador '{usuario_autenticado}' actualizó los metadatos del dataset con ID: {id_dataset}")
        registrar_evento_auditoria(db, usuario_autenticado, "Actualización", f"{datos.titulo} (ID: {id_dataset[:8]}...)")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500, 
            detail=f"Error al actualizar el dataset en la base vectorial: {str(e)}"
        )
    
    return {"mensaje": "Dataset actualizado exitosamente", "id": id_dataset}

@router.delete("/api/admin/datasets/{id_dataset}")
def eliminar_dataset(
    id_dataset: str, 
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    try:
        item_actual = coleccion.get(ids=[id_dataset], include=["documents"])
        nombre_dataset = item_actual["documents"][0] if item_actual and item_actual.get("documents") else id_dataset
        
        coleccion.delete(ids=[id_dataset])
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al limpiar la base de datos: {str(e)}"
        )

    ruta_csv = f"data/raw/{id_dataset}.csv"
    if os.path.exists(ruta_csv):
        os.remove(ruta_csv)
    
    # Registro dual: archivo plano y tabla de SQLite
    logger.info(f"[BITACORA AUDITORIA] El administrador '{usuario_autenticado}' eliminó el dataset con ID: {id_dataset}")
    registrar_evento_auditoria(db, usuario_autenticado, "Eliminación", f"{nombre_dataset} (ID: {id_dataset[:8]}...)")

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
        df.columns = df.columns.str.lower()
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