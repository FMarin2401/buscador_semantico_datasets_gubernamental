# Este script indexa en ChromaDB los datasets del catalogo revisado y copia sus CSV a data/raw.
# Es idempotente: se puede correr las veces que haga falta (por ejemplo, al cambiar de modelo de embeddings)
# sin duplicar datasets, sin cambiar sus IDs y sin perder los contadores de descargas.
#
# Uso (desde cualquier carpeta):
#   python scripts/migrate_chroma.py            # Indexa o actualiza
#   python scripts/migrate_chroma.py --simular  # Muestra que haria sin modificar nada

import os
import sys
import uuid
import shutil
import hashlib
import argparse
from datetime import datetime

RAIZ_PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(RAIZ_PROYECTO)
os.chdir(RAIZ_PROYECTO) # ChromaDB y las rutas del pipeline son relativas a la raiz del proyecto

import pandas as pd
from config_pipeline import CATALOGO_REVISADO, CARPETA_ORIGINALES, CARPETA_RAW_PRODUCCION, CATALOGO_GEMINI
from app.db_chroma import coleccion, guardar_o_actualizar_datasets, modelo_indexado, registrar_modelo_indexado
from app.nlp_model import NOMBRE_MODELO, generar_embeddings_documentos, texto_para_indexar

# Namespace fijo para generar IDs deterministas: el mismo archivo siempre produce el mismo UUID
NAMESPACE_DATASETS = uuid.UUID("1158df0d-6605-4cb7-b631-aa49df5c1f6e")
COLUMNAS_REQUERIDAS = ["archivo_original", "titulo", "descripcion", "dependencia", "categoria"]
CAMPOS_COMPARABLES = ["descripcion", "dependencia", "categoria", "hash_sha256"] # Si cambian, se actualiza la fecha


def cargar_catalogo():
    if not os.path.exists(CATALOGO_REVISADO):
        sys.exit(
            f"ERROR: No existe {CATALOGO_REVISADO}.\n"
            f"Ejecuta scripts/analyze_csv.py, revisa {CATALOGO_GEMINI} y guarda la version final como {CATALOGO_REVISADO}."
        )

    df = pd.read_csv(CATALOGO_REVISADO)
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        sys.exit(f"ERROR: Al catalogo le faltan las columnas {faltantes}.")

    duplicados = df[df["archivo_original"].duplicated()]["archivo_original"].tolist()
    if duplicados:
        sys.exit(f"ERROR: Archivos repetidos en el catalogo: {duplicados}")
    return df


def leer_indexados():
    # Separa los datasets ya indexados en dos grupos: los del catalogo (tienen archivo original)
    # y los subidos desde el panel (no lo tienen)
    datos = coleccion.get(include=["metadatas", "documents"])
    del_catalogo, del_panel = {}, []
    for id_dataset, titulo, meta in zip(datos["ids"], datos["documents"], datos["metadatas"]):
        registro = {"id": id_dataset, "titulo": titulo, "meta": meta or {}}
        if registro["meta"].get("archivo_original"):
            del_catalogo[registro["meta"]["archivo_original"]] = registro
        else:
            del_panel.append(registro)
    return del_catalogo, del_panel


def main():
    parser = argparse.ArgumentParser(description="Indexa el catalogo revisado en ChromaDB.")
    parser.add_argument("--simular", action="store_true", help="Muestra los cambios sin modificar ChromaDB ni data/raw")
    args = parser.parse_args()

    df_catalogo = cargar_catalogo()
    existentes, del_panel = leer_indexados()
    cambio_de_modelo = modelo_indexado() != NOMBRE_MODELO and bool(existentes or del_panel)
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    ids, textos, titulos, metadatas, copias = [], [], [], [], []
    resumen = {"nuevos": [], "actualizados": [], "sin cambios": [], "sin archivo": []}

    for _, row in df_catalogo.iterrows():
        archivo = row["archivo_original"]
        ruta_origen = os.path.join(CARPETA_ORIGINALES, archivo)
        if not os.path.exists(ruta_origen):
            resumen["sin archivo"].append(archivo)
            continue

        with open(ruta_origen, "rb") as f:
            hash_archivo = hashlib.sha256(f.read()).hexdigest() # Mismo hash que calcula el panel, para detectar duplicados

        previo = existentes.get(archivo)
        # Si ya estaba indexado se conserva su ID (aunque sea un uuid4 de versiones anteriores del script),
        # porque de el dependen el nombre del CSV en data/raw y el contador de descargas
        id_dataset = previo["id"] if previo else str(uuid.uuid5(NAMESPACE_DATASETS, archivo))

        metadata = {
            "dependencia": row["dependencia"],
            "categoria": row["categoria"],
            "descripcion": row["descripcion"],
            "archivo_original": archivo,
            "hash_sha256": hash_archivo,
        }

        sin_cambios = previo and previo["titulo"] == row["titulo"] and all(
            previo["meta"].get(campo) == metadata[campo] for campo in CAMPOS_COMPARABLES
        )
        metadata["fecha_actualizacion"] = previo["meta"].get("fecha_actualizacion", fecha_actual) if sin_cambios else fecha_actual
        resumen["sin cambios" if sin_cambios else "actualizados" if previo else "nuevos"].append(archivo)

        ruta_destino = os.path.join(CARPETA_RAW_PRODUCCION, f"{id_dataset}.csv")
        if not os.path.exists(ruta_destino) or not previo or previo["meta"].get("hash_sha256") != hash_archivo:
            copias.append((ruta_origen, ruta_destino))

        ids.append(id_dataset)
        titulos.append(row["titulo"])
        textos.append(texto_para_indexar(row["titulo"], row["descripcion"], row["dependencia"]))
        metadatas.append(metadata)

    # Los datasets subidos desde el panel no estan en el catalogo, pero sus vectores tambien deben generarse
    # con el modelo actual: se re-indexan con sus mismos metadatos
    for registro in del_panel:
        meta = registro["meta"]
        ids.append(registro["id"])
        titulos.append(registro["titulo"])
        textos.append(texto_para_indexar(registro["titulo"], meta.get("descripcion", ""), meta.get("dependencia", "")))
        metadatas.append(meta)

    # Datasets con archivo original que ya no estan en el catalogo: se avisan pero no se borran
    retirados = sorted(set(existentes) - set(df_catalogo["archivo_original"]))

    print(f"Modelo: {NOMBRE_MODELO} (indice actual: {modelo_indexado() or 'modelo anterior no registrado'})")
    if cambio_de_modelo:
        print("  CAMBIO DE MODELO: se recalculan los vectores de todos los datasets")
    print(f"Catalogo: {len(df_catalogo)} datasets | Ya indexados: {len(existentes)} del catalogo y {len(del_panel)} del panel")
    for etiqueta, archivos in resumen.items():
        print(f"  {etiqueta:<13} {len(archivos)}")
        if etiqueta != "sin cambios":
            for archivo in archivos:
                print(f"      - {archivo}")
    if retirados:
        print(f"  AVISO: {len(retirados)} datasets indexados ya no estan en el catalogo (no se borran): {retirados}")

    if args.simular:
        print(f"\nSimulacion: se re-indexarian {len(ids)} datasets y se copiarian {len(copias)} CSV. No se modifico nada.")
        return
    if not ids:
        print("\nNo hay datasets para indexar.")
        return

    os.makedirs(CARPETA_RAW_PRODUCCION, exist_ok=True)
    for ruta_origen, ruta_destino in copias:
        shutil.copyfile(ruta_origen, ruta_destino)

    # Se recalculan todos los embeddings (no solo los cambiados) para que un cambio de modelo re-indexe todo el catalogo
    embeddings = generar_embeddings_documentos(textos)
    guardar_o_actualizar_datasets(ids=ids, textos=titulos, embeddings=embeddings, metadatas=metadatas)
    registrar_modelo_indexado(NOMBRE_MODELO) # La app comprueba este dato al arrancar
    print(f"\nListo: {len(ids)} datasets indexados en ChromaDB y {len(copias)} CSV copiados a {CARPETA_RAW_PRODUCCION}")


if __name__ == "__main__":
    main()
