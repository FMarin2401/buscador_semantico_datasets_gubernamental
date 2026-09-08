# Este archivo contiene la logica principal de la API de FastAPI para el buscador semántico gubernamental

# Librerías estándar de Python
import json
import logging
import os
import shutil
import uuid
from datetime import datetime

# Librerías de terceros 
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status, Request
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import pandas as pd
from pydantic import BaseModel

# Módulos internos del proyecto
from app.database import buscar_similares, coleccion, guardar_datasets, obtener_todos_datasets
from app.nlp_model import generar_embedding

# Configuración de logging para depuración
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="API Buscador Semántico Gubernamental") # Crea un servidor FastAPI con el nombre de la API

app.mount("/data", StaticFiles(directory="data/raw"), name="data") # Converte la carpeta data/raw en un servidor de archivos estaticos para descarga

app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

templates = Jinja2Templates(directory="frontend")

# Configuración de CORS (solo para desarrollo, en producción se tiene que restringir los orígenes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Movemos el monitor de estado
@app.get("/api/status")
def status_check():
    return {"mensaje": "Servidor en línea."}

# Rutas Jinja2 para las vistas web
@app.get("/")
async def vista_inicio(request: Request):
    return templates.TemplateResponse(request,"index.html")

@app.get("/explorar_datos.html")
async def vista_datos(request: Request):
    return templates.TemplateResponse(request,"explorar_datos.html")


@app.get("/gobierno_abierto.html")
async def vista_gobierno_abierto(request: Request):
    return templates.TemplateResponse(request, "gobierno_abierto.html")

@app.get("/contacto.html")
async def vista_contacto(request: Request):
    return templates.TemplateResponse(request, "contacto.html")

@app.get("/noticias.html")
async def vista_noticias(request: Request):
    return templates.TemplateResponse(request, "noticias.html")

@app.get("/apis.html")
async def vista_apis(request: Request):
    return templates.TemplateResponse(request, "apis.html")

@app.get("/guia_usuario.html")
async def vista_guia(request: Request):
    return templates.TemplateResponse(request, "guia_usuario.html")

@app.get("/admin.html")
async def vista_admin(request: Request):
    return templates.TemplateResponse(request,"admin.html")

@app.get("/login.html")
async def vista_login(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/api/admin/datasets")
def listar_datasets_admin():
    datos = obtener_todos_datasets()
    resultados = []
    
    # Validamos que la base de datos no esté vacía
    if datos and datos.get("ids"):
        for i in range(len(datos["ids"])):
            meta = datos["metadatas"][i] if datos["metadatas"] else {}
            resultados.append({
                "id": datos["ids"][i],
                "titulo": datos["documents"][i],
                "dependencia": meta.get("dependencia", "No registrada"),
                "fecha": meta.get("fecha_actualizacion", "N/A")
            })
            
    return {"resultados": resultados}

@app.post("/api/admin/subir")
async def publicar_dataset(
    titulo: str = Form(...),
    descripcion: str = Form(...),
    dependencia: str = Form(...),
    archivo: UploadFile = File(...)
):
    # Filtro de seguridad: Validar que sea un archivo CSV
    if not archivo.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Solo se permiten archivos .csv"
        )
        
    # Doble filtro: Validar el tipo MIME interno del archivo
    if archivo.content_type not in ["text/csv", "application/vnd.ms-excel"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contenido del archivo no es un CSV válido."
        )

    # Generar el identificador único y las fechas
    id_unico = str(uuid.uuid4())
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    # Guardar el archivo físico usando el UUID como nombre para asegurar compatibilidad con descargas y borrados
    carpeta_destino = "data/raw"
    os.makedirs(carpeta_destino, exist_ok=True) 
    ruta_archivo = f"{carpeta_destino}/{id_unico}.csv"
    
    with open(ruta_archivo, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)
        
    # Generar el contexto de texto y su vector embedding
    texto_completo = f"{titulo}. {descripcion} Dependencia: {dependencia}"
    vector = generar_embedding(texto_completo) 
    
    # Preparar la estructura de metadatos
    metadata = {
        "dependencia": dependencia,
        "descripcion": descripcion,
        "fecha_actualizacion": fecha_actual
    }
    
    # Inyectar los datos a ChromaDB
    guardar_datasets(
        ids=[id_unico], 
        textos=[titulo], 
        embeddings=[vector],
        metadatas=[metadata]
    )
    
    return {
        "mensaje": "Dataset publicado exitosamente", 
        "id": id_unico,
        "archivo_guardado": archivo.filename
    }

@app.delete("/api/admin/datasets/{id_dataset}")
def eliminar_dataset(id_dataset: str):
    # 1. Eliminar el vector y metadatos de ChromaDB
    try:
        coleccion.delete(ids=[id_dataset])
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al limpiar la base de datos: {str(e)}"
        )

    # 2. Eliminar el archivo físico del disco
    ruta_csv = f"data/raw/{id_dataset}.csv"
    if os.path.exists(ruta_csv):
        os.remove(ruta_csv)
    
    return {"mensaje": "Dataset eliminado permanentemente"}

@app.get("/api/catalogos") 
def obtener_todo_el_catalogo():
    todos = coleccion.get(include=["documents", "metadatas"]) 
    
    catalogos_completos = [] 
    if todos and "documents" in todos: 
        documents = todos["documents"]
        metadatas = todos.get("metadatas", [])
        ids = todos.get("ids", []) # Recuperamos los IDs de ChromaDB
        
        for i in range(len(documents)): 
            documento = documents[i]
            id_actual = ids[i] if i < len(ids) else "" # Extraemos el ID actual

            meta = metadatas[i] if metadatas and i < len(metadatas) and metadatas[i] else {}
            dependencia = meta.get("dependencia", "No registrada")
            fecha_act = meta.get("fecha_actualizacion", "2026-01-01") 
            
            catalogos_completos.append({
                "id": id_actual, # Clave para que item.id funcione en el frontend
                "dataset_recomendado": documento,
                "dependencia": dependencia,
                "fecha_actualizacion": fecha_act,
                "distancia": 0.0 
            })
            
    return {"resultados": catalogos_completos}

@app.get("/api/buscar") 
def buscar_dataset(prompt: str):
    vector_prompt = generar_embedding(prompt) 
    
    n_meta = 15
    resultados = buscar_similares(vector_prompt, n_resultados=n_meta) 
    
    logger.debug("--- INICIO DE BÚSQUEDA ---") 
    logger.debug(f"Prompt del usuario: {prompt}")
    
    documents = resultados.get('documents', [[]])[0] 
    distances = resultados.get('distances', [[]])[0] 
    metadatas = resultados.get('metadatas', [[]])[0] 
    ids = resultados.get('ids', [[]])[0] # Extraemos los IDs de la búsqueda vectorial
    
    for idx, (doc, dist) in enumerate(zip(documents, distances)): 
        logger.debug(f"Top {idx + 1}: {doc} | Distancia: {dist}")
    logger.debug("------------------\n")
    
    umbral_maximo = 0.80 

    resultados_validos = [] 
    
    for i in range(len(distances)): 
        distancia = distances[i] 
        
        if distancia <= umbral_maximo: 
            documento = documents[i]

            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            dependencia = meta.get('dependencia', "No registrada") 
            fecha_act = meta.get("fecha_actualizacion", "2026-01-01") 
            
            resultados_validos.append({ 
                "id": ids[i] if i < len(ids) else "", # Clave aquí también
                "dataset_recomendado": documento,
                "dependencia": dependencia,
                "fecha_actualizacion": fecha_act,
                "distancia": round(distancia, 4)
            })

    return {"busqueda": prompt, "resultados": resultados_validos}

@app.get("/api/descargar/{id_dataset}")
def descargar_dataset(id_dataset: str, formato: str = "csv"):
    ruta_csv = f"data/raw/{id_dataset}.csv"
    
    if not os.path.exists(ruta_csv):
        raise HTTPException(status_code=404, detail="Dataset no encontrado")
        
    if formato == "csv":
        return FileResponse(path=ruta_csv, filename=f"{id_dataset}.csv", media_type="text/csv")
        
    # Leemos el archivo en memoria para las conversiones dinámicas
    df = pd.read_csv(ruta_csv)
    
    if formato == "json":
        json_data = df.to_json(orient="records")
        return Response(content=json_data, media_type="application/json", 
                        headers={"Content-Disposition": f"attachment; filename={id_dataset}.json"})
                        
    elif formato == "xml":
        # Hacemos una copia para no alterar el archivo original
        df_xml = df.copy()
        
        # Reemplazamos espacios y caracteres especiales por guiones bajos para cumplir con el estándar XML
        df_xml.columns = df_xml.columns.str.replace(r'\W+', '_', regex=True)
        
        # Generamos el XML
        xml_data = df_xml.to_xml(index=False)
        return Response(content=xml_data, media_type="application/xml", 
                        headers={"Content-Disposition": f"attachment; filename={id_dataset}.xml"})
                        
    elif formato == "geojson":
        features = []
        for _, row in df.iterrows():
            feature = {"type": "Feature", "properties": row.to_dict(), "geometry": None}
            
            # Intenta detectar columnas de mapa si existen en el CSV
            lat = row.get("latitud") or row.get("lat")
            lon = row.get("longitud") or row.get("lon")
            
            if pd.notna(lat) and pd.notna(lon):
                feature["geometry"] = {"type": "Point", "coordinates": [lon, lat]} # GeoJSON usa [longitud, latitud]
                
            features.append(feature)
            
        geojson_data = {"type": "FeatureCollection", "features": features}
        return Response(content=json.dumps(geojson_data), media_type="application/geo+json", 
                        headers={"Content-Disposition": f"attachment; filename={id_dataset}.geojson"})
    
    raise HTTPException(status_code=400, detail="Formato no soportado")

class CredencialesAdmin(BaseModel):
    usuario: str
    password: str

@app.post("/api/login")
def login_admin(credenciales: CredencialesAdmin):
    # Credenciales de ejemplo para el prototipo (puedes cambiarlas por variables de entorno)
    if credenciales.usuario == "admin" and credenciales.password == "admin123":
        # Generamos un token JWT simulado o firmado
        return {
            "access_token": "jwt-token-seguro-leon-2026",
            "token_type": "bearer"
        }
    raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

