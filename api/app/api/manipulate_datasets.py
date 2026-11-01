import os
import uuid
from uuid import UUID
import json
from datetime import datetime
from typing import Literal, Optional
import pandas as pd
import logging
import hashlib
import io
import csv

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status, Depends
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

# Módulos internos del proyecto
from app.catalogo import CATEGORIAS
from app.db_chroma import coleccion, guardar_datasets, obtener_todos_datasets
from app.nlp_model import generar_embedding_documento, texto_para_indexar
from app.api.auth import verificar_token, requiere_admin
from app.limiter import limiter
from app.db_core.connection import get_db
from app.db_core.models import BitacoraAuditoriaModel, DescargasDatasetModel, DatasetModel, UsuarioModel
from app.db_core.auditoria import registrar_evento_auditoria
from app.db_core.sincronizacion import valores_desde_chroma
from app.api.esquemas import MensajeRespuesta, ERROR_401, ERROR_403, ERROR_429, error

router = APIRouter(tags=["Gestión y Descarga de Datasets"])
logger = logging.getLogger(__name__)
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 26,214,400 bytes

# Límites de longitud para los metadatos (deben coincidir con los maxlength de frontend/admin.html)
MAX_TITULO = 200
MAX_DESCRIPCION = 2000
MAX_DEPENDENCIA = 200
MAX_CATEGORIA = 100

class DatasetActualizar(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=MAX_TITULO)
    descripcion: str = Field(..., min_length=1, max_length=MAX_DESCRIPCION)
    dependencia: str = Field(..., min_length=1, max_length=MAX_DEPENDENCIA)
    categoria: str = Field(..., min_length=1, max_length=MAX_CATEGORIA, description="Una de GET /api/categorias")

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "titulo": "Accidentes Viales 2026",
        "descripcion": "Registro de colisiones y percances viales con ubicación y daños, actualizado a octubre.",
        "dependencia": "Dirección General de Movilidad",
        "categoria": "Movilidad",
    }]})


class DatasetAdmin(BaseModel):
    id: str
    titulo: str
    descripcion: str
    dependencia: str
    categoria: str
    fecha: str = Field(description="Fecha de actualización AAAA-MM-DD, o N/A")


class ListaDatasetsAdmin(BaseModel):
    resultados: list[DatasetAdmin]

    model_config = ConfigDict(json_schema_extra={"examples": [{"resultados": [{
        "id": "6d1c0f3a-8b52-5e1e-9c41-2f0a7a1b9e10", "titulo": "Accidentes Viales",
        "descripcion": "Registro de colisiones y percances viales con ubicación y daños.",
        "dependencia": "Dirección General de Movilidad", "categoria": "Movilidad", "fecha": "2026-10-22",
    }]}]})


class EventoBitacora(BaseModel):
    id: int
    usuario: str = Field(description="Nombre del funcionario al momento del evento")
    usuario_id: Optional[int] = Field(description="Cuenta del funcionario; null si ya se borró")
    accion: str
    detalles: str
    fecha_hora: datetime = Field(description="UTC")

    model_config = ConfigDict(from_attributes=True)


class ListaBitacora(BaseModel):
    registros: list[EventoBitacora]

    model_config = ConfigDict(json_schema_extra={"examples": [{"registros": [{
        "id": 41, "usuario": "admin_leon", "usuario_id": 1, "accion": "Publicación",
        "detalles": "Accidentes Viales 2026 (Dirección General de Movilidad)", "fecha_hora": "2026-11-01T18:42:10",
    }]}]})


class DatasetPublicado(BaseModel):
    mensaje: str
    id: str = Field(description="UUID asignado al dataset")
    archivo_guardado: str = Field(description="Nombre del archivo que se subió")

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "mensaje": "Dataset publicado exitosamente", "id": "0b8f6c1e-3d2a-4c55-9a7e-1f2b3c4d5e6f", "archivo_guardado": "accidentes_2026.csv",
    }]})


class DatasetActualizado(BaseModel):
    mensaje: str
    id: str

    model_config = ConfigDict(json_schema_extra={"examples": [{"mensaje": "Dataset actualizado exitosamente", "id": "0b8f6c1e-3d2a-4c55-9a7e-1f2b3c4d5e6f"}]})


class VistaPrevia(BaseModel):
    columnas: list[str]
    filas: list[list[str]] = Field(description="Primeras filas, como texto y recortadas a 100 caracteres por celda")
    total_filas: int
    total_columnas: int

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "columnas": ["Folio", "Causa", "Interseccion"],
        "filas": [["ACC-101", "Alcance", "Blvd. Aeropuerto y Delta"], ["ACC-102", "Exceso de Velocidad", "Malecón del Río"]],
        "total_filas": 3,
        "total_columnas": 3,
    }]})


ERROR_DATASET_404 = error("El dataset no existe", "Dataset no encontrado")
ERROR_500_BASE = error("Falló la base vectorial o la relacional; el detalle queda en el log del servidor", "Error al guardar el dataset en la base vectorial.")

def validar_categoria(categoria: str):
    # Solo se aceptan las categorías oficiales: una escrita a mano crearía un filtro nuevo en el portal.
    # El mensaje es texto (no la lista de errores de Pydantic) para que el panel lo muestre tal cual.
    if categoria not in CATEGORIAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Categoría no válida. Usa una de las oficiales: {', '.join(CATEGORIAS)}."
        )

def es_csv_legible(contenido: bytes) -> bool:
    """Comprueba que el archivo se pueda leer como CSV con al menos una columna (se leen solo las primeras filas)."""
    if b"\x00" in contenido[:8192]:
        return False # Un CSV de texto nunca tiene bytes nulos; es un archivo binario (imagen, Excel, PDF...) renombrado
    for codificacion in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(contenido), nrows=50, encoding=codificacion)
            return len(df.columns) > 0
        except UnicodeDecodeError:
            continue # Se reintenta con latin-1, igual que al descargar
        except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError):
            return False
    return False

@router.get(
    "/api/admin/datasets",
    response_model=ListaDatasetsAdmin,
    summary="Catálogo para el panel",
    description="Todos los datasets con sus metadatos editables. Requiere sesión (administrador o editor).",
    responses={401: ERROR_401},
)
def listar_datasets_admin(usuario_autenticado: str = Depends(verificar_token)):
    datos = obtener_todos_datasets()
    resultados = []
    
    if datos and datos.get("ids"):
        for i in range(len(datos["ids"])):
            meta = datos["metadatas"][i] if datos["metadatas"] else {}
            resultados.append({
                "id": datos["ids"][i],
                "titulo": datos["documents"][i],
                "descripcion": meta.get("descripcion", ""),
                "dependencia": meta.get("dependencia", "No registrada"),
                "categoria": meta.get("categoria", "No registrada"),
                "fecha": meta.get("fecha_actualizacion", "N/A")
            })
            
    return {"resultados": resultados}

@router.get(
    "/api/admin/bitacora",
    response_model=ListaBitacora,
    summary="Últimos eventos de la bitácora",
    description="Los 15 eventos administrativos más recientes (publicaciones, ediciones, bajas, cambios de estado). Solo administradores.",
    responses={401: ERROR_401, 403: ERROR_403},
)
def obtener_bitacora(
    usuario_autenticado: str = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
    """Devuelve los últimos 15 eventos registrados para el panel de auditoría."""
    logs = db.query(BitacoraAuditoriaModel).order_by(BitacoraAuditoriaModel.fecha_hora.desc()).limit(15).all()
    return {"registros": logs}

# Es "def" y no "async def": generar el embedding usa CPU y bloquearía el event loop (y con él todas las búsquedas).
# FastAPI ejecuta los endpoints "def" en un threadpool, así que el servidor sigue atendiendo otras peticiones.
@router.post(
    "/api/admin/subir",
    status_code=status.HTTP_201_CREATED,
    response_model=DatasetPublicado,
    summary="Publicar un dataset",
    description=(
        "Recibe un CSV (máximo 25 MB) y sus metadatos como `multipart/form-data`. Genera el embedding, lo indexa en "
        "ChromaDB y lo registra en la tabla `datasets`. Reglas: la categoría debe ser oficial; el archivo debe poder "
        "leerse como CSV (no basta con la extensión); el mismo archivo (mismo SHA-256) no se puede publicar dos veces. "
        "Requiere sesión (administrador o editor)."
    ),
    responses={
        400: error("El archivo no es .csv o su contenido no es un CSV válido", "El contenido del archivo no es un CSV válido."),
        401: ERROR_401,
        409: error("El mismo archivo ya está publicado", "Este dataset ya fue subido anteriormente (Duplicado detectado)."),
        413: error("El archivo supera 25 MB", "El archivo excede el tamaño máximo permitido de 25 MB."),
        422: error("Categoría no oficial o campos fuera de los límites", "Categoría no válida. Usa una de las oficiales: Movilidad, Medio Ambiente, ..."),
        500: ERROR_500_BASE,
    },
)
def publicar_dataset(
    titulo: str = Form(..., min_length=1, max_length=MAX_TITULO, examples=["Accidentes Viales 2026"]),
    descripcion: str = Form(..., min_length=1, max_length=MAX_DESCRIPCION, examples=["Registro de colisiones y percances viales con ubicación y daños."]),
    dependencia: str = Form(..., min_length=1, max_length=MAX_DEPENDENCIA, examples=["Dirección General de Movilidad"]),
    categoria: str = Form(..., min_length=1, max_length=MAX_CATEGORIA, description="Una de GET /api/categorias", examples=["Movilidad"]),
    archivo: UploadFile = File(..., description="Archivo .csv de hasta 25 MB"),
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    validar_categoria(categoria)

    if not archivo.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Solo se permiten archivos .csv"
        )

    contenido_archivo = archivo.file.read() # En un endpoint "def" se usa el archivo síncrono subyacente

    if len(contenido_archivo) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo excede el tamaño máximo permitido de {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    # El content_type lo manda el navegador y se puede falsificar (o variar según el sistema operativo);
    # lo confiable es comprobar que pandas pueda leerlo como CSV
    if not es_csv_legible(contenido_archivo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contenido del archivo no es un CSV válido."
        )

    hash_calculado = hashlib.sha256(contenido_archivo).hexdigest()

    # Se filtra por hash en ChromaDB en lugar de traer toda la colección
    if coleccion.get(where={"hash_sha256": hash_calculado}, limit=1)["ids"]:
        logger.warning(f"[ALERTA] Ingesta bloqueada por duplicidad: {archivo.filename}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este dataset ya fue subido anteriormente (Duplicado detectado)."
        )

    id_unico = str(uuid.uuid4())
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    # El embedding se genera antes de escribir nada: si falla, no queda ningún archivo a medias
    vector = generar_embedding_documento(texto_para_indexar(titulo, descripcion, dependencia))

    metadata = {
        "dependencia": dependencia,
        "categoria": categoria,
        "descripcion": descripcion,
        "fecha_actualizacion": fecha_actual,
        "hash_sha256": hash_calculado
    }

    carpeta_destino = "data/raw"
    os.makedirs(carpeta_destino, exist_ok=True)
    ruta_archivo = f"{carpeta_destino}/{id_unico}.csv"

    with open(ruta_archivo, "wb") as buffer:
        buffer.write(contenido_archivo)

    try:
        guardar_datasets(
            ids=[id_unico],
            textos=[titulo],
            embeddings=[vector],
            metadatas=[metadata]
        )
    except Exception:
        # Si ChromaDB falla, se borra el CSV para no dejar un archivo huérfano en data/raw
        os.remove(ruta_archivo)
        logger.exception(f"Error al guardar el dataset '{titulo}' en ChromaDB")
        raise HTTPException(
            status_code=500,
            detail="Error al guardar el dataset en la base vectorial."
        )

    # Registro relacional y evento de bitácora en una sola transacción. Si falla, se deshace lo de ChromaDB y el
    # archivo, para que las dos bases no queden con catálogos distintos
    try:
        publicado_por_id = db.query(UsuarioModel.id).filter(UsuarioModel.username == usuario_autenticado).scalar()
        db.add(DatasetModel(id=id_unico, publicado_por_id=publicado_por_id, **valores_desde_chroma(titulo, metadata)))
        registrar_evento_auditoria(db, usuario_autenticado, "Publicación", f"{titulo} ({dependencia})")
        db.commit()
    except Exception:
        db.rollback()
        coleccion.delete(ids=[id_unico])
        os.remove(ruta_archivo)
        logger.exception(f"Error al registrar el dataset '{titulo}' en la base relacional")
        raise HTTPException(
            status_code=500,
            detail="Error al guardar el dataset en la base de datos."
        )

    logger.info(f"[BITACORA AUDITORIA] El usuario '{usuario_autenticado}' subió el dataset '{titulo}' con ID: {id_unico}.")

    return {
        "mensaje": "Dataset publicado exitosamente", 
        "id": id_unico,
        "archivo_guardado": archivo.filename
    }

@router.put(
    "/api/admin/datasets/{id_dataset}",
    response_model=DatasetActualizado,
    summary="Editar los metadatos de un dataset",
    description="Reemplaza título, descripción, dependencia y categoría, y recalcula su embedding. El archivo no cambia. Requiere sesión (administrador o editor).",
    responses={
        401: ERROR_401,
        404: error("El dataset no existe", "Dataset no encontrado en la base de datos."),
        422: error("Categoría no oficial, campos vacíos o un ID que no es UUID", "Categoría no válida. Usa una de las oficiales: Movilidad, Medio Ambiente, ..."),
        500: error("Falló la base vectorial o la relacional", "Error al actualizar el dataset en la base vectorial."),
    },
)
def actualizar_dataset(
    id_dataset: UUID, # Declararlo como UUID rechaza cualquier otro valor antes de usarlo en consultas o rutas
    datos: DatasetActualizar,
    usuario_autenticado: str = Depends(verificar_token),
    db: Session = Depends(get_db)
):
    id_dataset = str(id_dataset)
    validar_categoria(datos.categoria)
    try:
        item_actual = coleccion.get(ids=[id_dataset], include=["metadatas", "documents"])
        if not item_actual or not item_actual.get("ids"):
            raise HTTPException(status_code=404, detail="Dataset no encontrado en la base de datos.")

        meta_vieja = (item_actual["metadatas"][0] if item_actual["metadatas"] else None) or {}
        fecha_actual = datetime.now().strftime("%Y-%m-%d")

        # Se parte de los metadatos existentes para conservar hash_sha256 y archivo_original:
        # sin archivo_original, migrate_chroma.py no reconocería el dataset y crearía un duplicado
        nuevo_metadata = {
            **meta_vieja,
            "dependencia": datos.dependencia,
            "categoria": datos.categoria,
            "descripcion": datos.descripcion,
            "fecha_actualizacion": fecha_actual,
        }

        nuevo_vector = generar_embedding_documento(texto_para_indexar(datos.titulo, datos.descripcion, datos.dependencia))

        coleccion.update(
            ids=[id_dataset],
            documents=[datos.titulo],
            embeddings=[nuevo_vector],
            metadatas=[nuevo_metadata]
        )

        # Mismos valores en la tabla relacional (si faltara la fila, se crea; la sincronización del arranque la habría creado)
        valores = valores_desde_chroma(datos.titulo, nuevo_metadata)
        fila = db.get(DatasetModel, id_dataset)
        if fila:
            for campo, valor in valores.items():
                setattr(fila, campo, valor)
        else:
            db.add(DatasetModel(id=id_dataset, **valores))
        registrar_evento_auditoria(db, usuario_autenticado, "Actualización", f"{datos.titulo} (ID: {id_dataset[:8]}...)")
        db.commit()
        logger.info(f"[BITACORA AUDITORIA] El usuario '{usuario_autenticado}' actualizó los metadatos del dataset con ID: {id_dataset}")

    except HTTPException:
        raise
    except Exception:
        # El detalle completo va al log; al cliente solo un mensaje genérico para no exponer rutas ni versiones
        logger.exception(f"Error al actualizar el dataset {id_dataset}")
        raise HTTPException(
            status_code=500,
            detail="Error al actualizar el dataset en la base vectorial."
        )
    
    return {"mensaje": "Dataset actualizado exitosamente", "id": id_dataset}

@router.delete(
    "/api/admin/datasets/{id_dataset}",
    response_model=MensajeRespuesta,
    summary="Eliminar un dataset",
    description="Lo borra de ChromaDB, de la tabla `datasets` (con su contador de descargas y sus reportes) y borra su archivo. Solo administradores.",
    responses={
        401: ERROR_401,
        403: ERROR_403,
        404: error("El dataset no existe", "Dataset no encontrado en la base de datos."),
        500: error("Falló la base vectorial", "Error al limpiar la base de datos."),
    },
)
def eliminar_dataset(
    id_dataset: UUID,
    usuario_autenticado: str = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
    id_dataset = str(id_dataset)
    try:
        item_actual = coleccion.get(ids=[id_dataset], include=["documents"])
    except Exception:
        logger.exception(f"Error al consultar el dataset {id_dataset}")
        raise HTTPException(status_code=500, detail="Error al limpiar la base de datos.")
    if not item_actual or not item_actual.get("ids"):
        raise HTTPException(status_code=404, detail="Dataset no encontrado en la base de datos.")
    nombre_dataset = item_actual["documents"][0] if item_actual.get("documents") else id_dataset

    try:
        coleccion.delete(ids=[id_dataset])
    except Exception:
        logger.exception(f"Error al eliminar el dataset {id_dataset}")
        raise HTTPException(
            status_code=500,
            detail="Error al limpiar la base de datos."
        )

    ruta_csv = f"data/raw/{id_dataset}.csv"
    if os.path.exists(ruta_csv):
        os.remove(ruta_csv)

    # Al borrar la fila se borran también su contador de descargas y sus reportes (cascada en el ORM y en PostgreSQL)
    fila = db.get(DatasetModel, id_dataset)
    if fila:
        db.delete(fila)

    # Registro dual: archivo plano y tabla relacional
    logger.info(f"[BITACORA AUDITORIA] El usuario '{usuario_autenticado}' eliminó el dataset con ID: {id_dataset}")
    registrar_evento_auditoria(db, usuario_autenticado, "Eliminación", f"{nombre_dataset} (ID: {id_dataset[:8]}...)")
    db.commit()

    return {"mensaje": "Dataset eliminado permanentemente"}

def leer_csv(ruta_csv: str, **opciones) -> pd.DataFrame:
    # Los CSV del municipio llegan en UTF-8 o en latin-1 (exportados desde Excel)
    try:
        return pd.read_csv(ruta_csv, encoding="utf-8", **opciones)
    except UnicodeDecodeError:
        return pd.read_csv(ruta_csv, encoding="latin-1", **opciones)

FILAS_VISTA_PREVIA = 5
MAX_CARACTERES_CELDA = 100

@router.get(
    "/api/datasets/{id_dataset}/vista-previa",
    response_model=VistaPrevia,
    summary="Vista previa de un dataset",
    description="Columnas y primeras 5 filas, para la ficha técnica. Público, no cuenta como descarga. Límite: 30 por minuto por IP.",
    responses={404: ERROR_DATASET_404, 429: ERROR_429},
)
@limiter.limit("30/minute") # Muestra solo unas filas, pero sin límite serviría para leer los archivos en masa
def vista_previa_dataset(request: Request, id_dataset: UUID):
    """Columnas y primeras filas de un dataset, para la ficha técnica. No suma al contador de descargas."""
    ruta_csv = f"data/raw/{id_dataset}.csv"
    if not os.path.exists(ruta_csv):
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    # Todo como texto y sin convertir vacíos a NaN: se muestra el valor tal como está en el archivo
    # (si no, pandas convierte "1" en "1.0" en una columna numérica con celdas vacías)
    df = leer_csv(ruta_csv, dtype=str, keep_default_na=False)
    return {
        "columnas": [str(c) for c in df.columns],
        "filas": [[v[:MAX_CARACTERES_CELDA] for v in fila] for fila in df.head(FILAS_VISTA_PREVIA).values.tolist()],
        "total_filas": len(df),
        "total_columnas": len(df.columns),
    }

@router.get(
    "/api/descargar/{id_dataset}",
    summary="Descargar un dataset",
    description=(
        "Público. Devuelve el archivo en el formato pedido: el CSV original, o convertido al vuelo a JSON, XML o GeoJSON "
        "(el GeoJSON toma las columnas `latitud`/`longitud` o `lat`/`lon`). Suma una descarga al contador del dataset."
    ),
    response_class=Response,
    responses={
        200: {
            "description": "Archivo como adjunto (Content-Disposition: attachment)",
            "content": {
                "text/csv": {"example": "Folio,Causa\nACC-101,Alcance\n"},
                "application/json": {"example": [{"Folio": "ACC-101", "Causa": "Alcance"}]},
                "application/xml": {"example": "<data><row><Folio>ACC-101</Folio></row></data>"},
                "application/geo+json": {"example": {"type": "FeatureCollection", "features": []}},
            },
        },
        404: ERROR_DATASET_404,
        422: {"description": "Formato distinto de csv, json, xml o geojson, o un ID que no es UUID"},
    },
)
def descargar_dataset(
    id_dataset: UUID,
    formato: Literal["csv", "json", "xml", "geojson"] = Query("csv", description="Formato del archivo"), # Un formato inválido se rechaza (422) antes de contar la descarga
    db: Session = Depends(get_db)
):
    id_dataset = str(id_dataset) # Solo un UUID válido llega a construir la ruta del archivo
    ruta_csv = f"data/raw/{id_dataset}.csv"
    # El contador tiene llave foránea a datasets: sin la fila, el dataset no existe para la base relacional
    if not os.path.exists(ruta_csv) or not db.get(DatasetModel, id_dataset):
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    registro = db.query(DescargasDatasetModel).filter(DescargasDatasetModel.id_dataset == id_dataset).first()
    if not registro:
        registro = DescargasDatasetModel(id_dataset=id_dataset, total_descargas=1)
        db.add(registro)
    else:
        registro.total_descargas += 1
    db.commit()
      
    if formato == "csv":
        return FileResponse(path=ruta_csv, filename=f"{id_dataset}.csv", media_type="text/csv")
        
    df = leer_csv(ruta_csv)

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

@router.get(
    "/api/admin/bitacora/exportar",
    summary="Exportar la bitácora completa",
    description="Todos los eventos de auditoría en un CSV (fechas en UTC). Solo administradores.",
    response_class=Response,
    responses={
        200: {"description": "CSV como adjunto", "content": {"text/csv": {"example": "ID,Usuario,Accion,Detalles,Fecha_Hora_UTC\n41,admin_leon,Publicación,Accidentes Viales 2026,2026-11-01 18:42:10\n"}}},
        401: ERROR_401,
        403: ERROR_403,
    },
)
def exportar_bitacora_csv(
    usuario_autenticado: str = Depends(requiere_admin),
    db: Session = Depends(get_db)
):
    """Genera y descarga un reporte CSV con el historial completo de auditoría."""
    registros = db.query(BitacoraAuditoriaModel).order_by(BitacoraAuditoriaModel.fecha_hora.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    
    # Encabezados del reporte
    writer.writerow(["ID", "Usuario", "Accion", "Detalles", "Fecha_Hora_UTC"])

    for log in registros:
        writer.writerow([
            log.id,
            log.usuario,
            log.accion,
            log.detalles,
            log.fecha_hora.strftime("%Y-%m-%d %H:%M:%S") if log.fecha_hora else ""
        ])

    csv_data = buffer.getvalue()
    buffer.close()

    fecha_hoy = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_archivo = f"bitacora_auditoria_{fecha_hoy}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
    )