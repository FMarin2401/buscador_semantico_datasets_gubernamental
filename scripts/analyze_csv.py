# Este script usa Gemini para generar los metadatos (titulo, descripcion, dependencia y categoria) de cada CSV del municipio.
# El resultado se guarda en CATALOGO_GEMINI y debe revisarlo una persona antes de indexarlo (ver config_pipeline.py).
#
# PRIVACIDAD: por cada CSV se envian a la API de Google las primeras filas como muestra.
# Si un archivo contiene datos personales, usa --solo-columnas para enviar unicamente los nombres de las columnas.
#
# Uso (desde cualquier carpeta):
#   python scripts/analyze_csv.py                   # Procesa solo los CSV que aun no estan en el catalogo
#   python scripts/analyze_csv.py --forzar          # Vuelve a procesar todos
#   python scripts/analyze_csv.py --solo-columnas   # No envia filas de datos, solo encabezados

import os
import sys
import enum
import time
import random
import argparse

RAIZ_PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(RAIZ_PROYECTO) # Las rutas del pipeline son relativas a la raiz del proyecto

import httpx
import pandas as pd
from pydantic import BaseModel, Field
from google import genai
from google.genai import errors, types
from dotenv import load_dotenv
from config_pipeline import CARPETA_ORIGINALES, CATALOGO_GEMINI, CATALOGO_REVISADO, CATEGORIAS

load_dotenv()
MODELO_GEMINI = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
FILAS_MUESTRA = 5 # Pocas filas bastan para entender las columnas y ahorran tokens
MAX_INTENTOS = 5

# Con un Enum, Gemini solo puede responder una de las categorias oficiales (y Pydantic rechaza cualquier otra)
Categoria = enum.Enum("Categoria", [(c, c) for c in CATEGORIAS], type=str)


class MetadatosDataset(BaseModel):
    titulo: str = Field(description="Nombre formal y corto para el dataset.")
    descripcion: str = Field(description=(
        "Qué contiene exactamente, en máximo 2 líneas. Incluye sinónimos del título y palabras que la ciudadanía "
        "teclea al buscar, como 'teléfono', 'contacto', 'horarios' o 'citas'."
    ))
    dependencia: str = Field(description=(
        "Dependencia oficial completa del Municipio de León responsable de los datos "
        "(ej. Secretaría de Seguridad, Prevención y Protección Ciudadana; Dirección General de Movilidad)."
    ))
    categoria: Categoria = Field(description="Categoría para los filtros del buscador.")


def crear_prompt(nombre_archivo: str, muestra: str) -> str:
    return (
        "Eres un analista de datos del Municipio de León. "
        "Genera los metadatos de este dataset a partir de su nombre de archivo y una muestra de su contenido.\n"
        f"Archivo: {nombre_archivo}\n"
        f"Muestra: {muestra}"
    )


def analizar_csv_con_ia(cliente: genai.Client, nombre_archivo: str, muestra: str) -> MetadatosDataset:
    # Salida estructurada: Gemini responde JSON que cumple el esquema, sin limpiar bloques ```json a mano
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=MetadatosDataset,
    )
    respuesta = llamar_con_reintentos(lambda: cliente.models.generate_content(
        model=MODELO_GEMINI,
        contents=crear_prompt(nombre_archivo, muestra),
        config=config,
    ))
    if respuesta.parsed is None:
        raise ValueError(f"Gemini no devolvio un JSON valido: {respuesta.text!r}")
    return respuesta.parsed


def llamar_con_reintentos(funcion):
    # Reintenta solo ante errores temporales (429 por limite de uso, 5xx o fallas de red),
    # esperando cada vez el doble: 2, 4, 8, 16 segundos (+ un poco de azar para no sincronizar reintentos)
    espera = 2
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            return funcion()
        except (errors.APIError, httpx.TransportError) as e:
            codigo = getattr(e, "code", None)
            es_temporal = codigo is None or codigo == 429 or codigo >= 500
            if not es_temporal or intento == MAX_INTENTOS:
                raise
            print(f"   Error temporal ({codigo or type(e).__name__}); reintento {intento}/{MAX_INTENTOS - 1} en {espera} s...")
            time.sleep(espera + random.uniform(0, 1))
            espera *= 2


def leer_muestra(ruta: str, solo_columnas: bool) -> str:
    try:
        df = pd.read_csv(ruta, nrows=FILAS_MUESTRA, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(ruta, nrows=FILAS_MUESTRA, encoding="latin-1")
    if solo_columnas:
        return "Columnas: " + ", ".join(map(str, df.columns))
    return df.to_json(orient="records", force_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Genera metadatos de los CSV del municipio con Gemini.")
    parser.add_argument("--forzar", action="store_true", help="Vuelve a procesar los CSV que ya estan en el catalogo")
    parser.add_argument("--solo-columnas", action="store_true", help="Envia solo los nombres de las columnas, sin filas de datos")
    args = parser.parse_args()

    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("ERROR: Falta GEMINI_API_KEY en el .env")
    if not os.path.exists(CARPETA_ORIGINALES):
        os.makedirs(CARPETA_ORIGINALES)
        sys.exit(f"Crea la carpeta '{CARPETA_ORIGINALES}' y coloca los CSV del municipio ahi.")

    # Si ya hay un catalogo previo, se conservan sus filas y solo se procesan los archivos nuevos
    catalogo = []
    if os.path.exists(CATALOGO_GEMINI) and not args.forzar:
        catalogo = pd.read_csv(CATALOGO_GEMINI).to_dict("records")
    ya_procesados = {fila["archivo_original"] for fila in catalogo}

    pendientes = sorted(a for a in os.listdir(CARPETA_ORIGINALES) if a.endswith(".csv") and a not in ya_procesados)
    print(f"Modelo: {MODELO_GEMINI} | Ya procesados: {len(ya_procesados)} | Pendientes: {len(pendientes)}")

    cliente = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    errores = []
    for archivo in pendientes:
        print(f"Analizando {archivo} con IA...")
        try:
            muestra = leer_muestra(os.path.join(CARPETA_ORIGINALES, archivo), args.solo_columnas)
            metadatos = analizar_csv_con_ia(cliente, archivo, muestra)
        except Exception as e:
            print(f"   Error procesando {archivo}: {e}")
            errores.append(archivo)
            continue

        catalogo.append({"archivo_original": archivo, **metadatos.model_dump(mode="json")})
        # Se guarda despues de cada archivo: si el proceso se interrumpe, no se pierde lo ya pagado en tokens
        os.makedirs(os.path.dirname(CATALOGO_GEMINI), exist_ok=True)
        pd.DataFrame(catalogo).to_csv(CATALOGO_GEMINI, index=False)

    print(f"\nCatalogo con {len(catalogo)} datasets guardado en {CATALOGO_GEMINI}")
    if errores:
        print(f"No se pudieron procesar {len(errores)} archivos (vuelve a correr el script para reintentarlos): {errores}")
    print(f"Siguiente paso: revisa {CATALOGO_GEMINI}, guarda la version final como {CATALOGO_REVISADO} "
          f"y ejecuta scripts/migrate_chroma.py")


if __name__ == "__main__":
    main()
