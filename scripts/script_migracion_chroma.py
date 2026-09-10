import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import uuid
import shutil
import pandas as pd
from datetime import datetime
from app.database import guardar_datasets
from app.nlp_model import generar_embedding

# Rutas 
CATALOGO = "data/clean/catalogo_maestro.csv"
CARPETA_ORIGINALES = "data/entregados_municipio/"
CARPETA_RAW_PRODUCCION = "data/raw/"

os.makedirs(CARPETA_RAW_PRODUCCION, exist_ok=True)
df_catalogo = pd.read_csv(CATALOGO)

ids = []
textos = []
embeddings = []
metadatas = []
fecha_actual = datetime.now().strftime("%Y-%m-%d")

for index, row in df_catalogo.iterrows():
    id_unico = str(uuid.uuid4())
    archivo_origen = os.path.join(CARPETA_ORIGINALES, row["archivo_original"])
    archivo_destino = os.path.join(CARPETA_RAW_PRODUCCION, f"{id_unico}.csv")
    
    # Copiamos el archivo físico con su nuevo ID seguro
    shutil.copyfile(archivo_origen, archivo_destino)
    
    # Generamos el texto para la IA
    texto_busqueda = f"{row['titulo']}. {row['descripcion']} Dependencia: {row['dependencia']}"
    vector = generar_embedding(texto_busqueda)
    
    # Preparamos las listas para ChromaDB
    ids.append(id_unico)
    textos.append(row["titulo"])
    embeddings.append(vector)
    metadatas.append({
        "dependencia": row["dependencia"],
        "categoria": row["categoria"],
        "descripcion": row["descripcion"],
        "fecha_actualizacion": fecha_actual,
        "archivo_original": row["archivo_original"]
    })
    print(f"Procesado: {row['titulo']} -> Categoría: {row['categoria']}")

# Inyección masiva 
guardar_datasets(ids=ids, textos=textos, embeddings=embeddings, metadatas=metadatas)
print("¡Migración a producción completada!")