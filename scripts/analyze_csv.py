import os
import time
import json
import pandas as pd
from google import genai
from dotenv import load_dotenv

# Cargar variables de entorno y configurar el cliente oficial de Gemini
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

CARPETA_ORIGINALES = "data/entregados_municipio/"
CATALOGO_SALIDA = "data/clean/catalogo_maestro_procesado.csv"

def analizar_csv_con_ia(nombre_archivo, muestra_datos):
    prompt = f"""
    Eres un analista de datos del Municipio de León. Analiza esta muestra de datos:
    Archivo: {nombre_archivo}
    Datos: {muestra_datos}
    
    Devuelve ÚNICAMENTE un JSON válido con estas claves exactas sin formato markdown:
    {{
        "titulo": "Un nombre formal y corto para el dataset.",
        "descripcion": "Qué contiene exactamente e incluye sinónimos del titulo y palabras clave comunes que la ciudadania teclea como 'teléfono', 'contacto', 'horarios' o 'citas' (máximo 2 líneas).",
        "dependencia": "La dependencia oficial completa del Municipio de León responsable de estos datos (ej. Secretaría de Seguridad, Prevención y Protección Ciudadana, Dirección General de Movilidad, etc.)",
        "categoria": "Una categoría corta y limpia para filtros (ej. Seguridad, Movilidad, Educación, Salud, Desarrollo Social, Medio Ambiente, Economía), eliminando prefijos largos como 'Secretaría de' o 'Dirección General de'."
    }}
    """
    
    # Llamada usando el SDK oficial con el modelo flash actual
    respuesta = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
    )
    
    # Limpieza de etiquetas markdown por si el modelo responde con bloques de código
    texto_limpio = respuesta.text.replace('```json', '').replace('```', '').strip()
    return json.loads(texto_limpio)

datos_catalogo = []

if not os.path.exists(CARPETA_ORIGINALES):
    os.makedirs(CARPETA_ORIGINALES)
    print(f"Crea la carpeta '{CARPETA_ORIGINALES}' y coloca los CSVs del municipio ahí.")
else:
    for archivo in os.listdir(CARPETA_ORIGINALES):
        if archivo.endswith(".csv"):
            ruta_completa = os.path.join(CARPETA_ORIGINALES, archivo)
            
            # Leemos solo 5 filas para no gastar tokens ni saturar la memoria
            df_muestra = pd.read_csv(ruta_completa, nrows=5)
            muestra_json = df_muestra.to_json(orient="records")
            
            print(f"Analizando {archivo} con IA...")
            try:
                metadatos = analizar_csv_con_ia(archivo, muestra_json)
                datos_catalogo.append({
                    "archivo_original": archivo,
                    "titulo": metadatos["titulo"],
                    "descripcion": metadatos["descripcion"],
                    "dependencia": metadatos["dependencia"],
                    "categoria": metadatos["categoria"]
                })
            except Exception as e:
                print(f"Error procesando {archivo}: {e}")

            # Pausa de 10 segundos para darle respiro a la API entre llamadas
            time.sleep(10)

    if datos_catalogo:
        df_final = pd.DataFrame(datos_catalogo)
        df_final.to_csv(CATALOGO_SALIDA, index=False)
        print(f"¡Catálogo maestro guardado con éxito en {CATALOGO_SALIDA} con la nueva columna de categoría!")