# Este script compara varios modelos de embeddings contra el Ground Truth sin modificar ChromaDB.
# Lee los textos de los datasets ya indexados, los vuelve a codificar en memoria con cada modelo
# y calcula las mismas metricas que evaluate_model.py, ademas de las distancias para calibrar el umbral.
#
# Uso (desde cualquier carpeta):
#   python scripts/comparar_modelos.py                       # Todos los modelos del catalogo
#   python scripts/comparar_modelos.py minilm e5-small       # Solo algunos
#   python scripts/comparar_modelos.py --salida eval/resultados/comparacion.json
#
# La primera vez descarga cada modelo de Hugging Face (de 0.5 a 2 GB cada uno).

import os
import sys
import json
import argparse
from datetime import datetime

RAIZ_PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(RAIZ_PROYECTO)
os.chdir(RAIZ_PROYECTO) # ChromaDB usa la ruta relativa ./data/chroma_db

import numpy as np
from sentence_transformers import SentenceTransformer
from app.db_chroma import obtener_todos_datasets

GROUND_TRUTH = "eval/ground_truth.json"

# clave: (modelo en Hugging Face, prefijo de consulta, prefijo de documento)
# Los modelos e5 se entrenaron con prefijos "query: " y "passage: "; sin ellos rinden bastante peor
CATALOGO_MODELOS = {
    "minilm": ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "", ""), # Modelo actual en produccion
    "mpnet": ("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "", ""),
    "e5-small": ("intfloat/multilingual-e5-small", "query: ", "passage: "),
    "e5-base": ("intfloat/multilingual-e5-base", "query: ", "passage: "),
}

# Consultas que no tienen nada que ver con datos municipales: sirven para ver a que distancia queda "lo irrelevante"
CONSULTAS_AJENAS = [
    "receta de pastel de chocolate",
    "quién ganó el mundial de fútbol",
    "cómo instalar python en windows",
    "letra de una canción de amor",
    "precio del bitcoin hoy",
    "mejores series de netflix",
]


def cargar_datasets():
    # Reconstruimos el mismo texto que se indexa en migrate_chroma.py y manipulate_datasets.py
    datos = obtener_todos_datasets()
    textos = [
        f"{titulo}. {meta['descripcion']} Dependencia: {meta['dependencia']}"
        for titulo, meta in zip(datos["documents"], datos["metadatas"])
    ]
    archivos = [meta.get("archivo_original", "") for meta in datos["metadatas"]]
    return textos, archivos


def evaluar_modelo(clave: str, textos: list, archivos: list, consultas: list):
    nombre, prefijo_consulta, prefijo_documento = CATALOGO_MODELOS[clave]
    modelo = SentenceTransformer(nombre)

    largos = [len(modelo.tokenizer(t)["input_ids"]) for t in textos]
    truncados = sum(1 for largo in largos if largo > modelo.max_seq_length) # Si hay truncados, el modelo no ve el texto completo

    # Con vectores normalizados, el producto punto es la similitud coseno (distancia = 1 - similitud, igual que en ChromaDB)
    vectores_docs = modelo.encode([prefijo_documento + t for t in textos], normalize_embeddings=True, batch_size=16)
    vectores_consultas = modelo.encode([prefijo_consulta + c["consulta"] for c in consultas], normalize_embeddings=True, batch_size=16)
    vectores_ajenas = modelo.encode([prefijo_consulta + c for c in CONSULTAS_AJENAS], normalize_embeddings=True)

    similitudes = vectores_consultas @ vectores_docs.T
    orden = np.argsort(-similitudes, axis=1)

    posiciones = []
    distancias_correcto = []
    for i, item in enumerate(consultas):
        ranking = [archivos[j] for j in orden[i]]
        posiciones.append(ranking.index(item["target"]) + 1 if item["target"] in ranking else len(ranking) + 1)
        if item["target"] in archivos:
            distancias_correcto.append(1 - similitudes[i, archivos.index(item["target"])])
    posiciones = np.array(posiciones)

    distancias_ajenas = 1 - (vectores_ajenas @ vectores_docs.T).max(axis=1) # Distancia al dataset mas parecido

    return {
        "modelo": nombre,
        "dimensiones": int(vectores_docs.shape[1]),
        "max_tokens": modelo.max_seq_length,
        "docs_truncados": truncados,
        "recall_1": round(100 * float((posiciones <= 1).mean()), 2),
        "recall_5": round(100 * float((posiciones <= 5).mean()), 2),
        "recall_10": round(100 * float((posiciones <= 10).mean()), 2),
        "mrr": round(float((1 / posiciones).mean()), 4),
        "distancia_correcto_p50": round(float(np.percentile(distancias_correcto, 50)), 4),
        "distancia_correcto_p90": round(float(np.percentile(distancias_correcto, 90)), 4),
        "distancia_correcto_max": round(float(np.max(distancias_correcto)), 4),
        "distancia_ajenas_min": round(float(distancias_ajenas.min()), 4),
        "distancia_ajenas_p50": round(float(np.median(distancias_ajenas)), 4),
    }


def imprimir_tabla(resultados: dict):
    print("\n" + "=" * 96)
    print(f"{'Modelo':<10} {'Dim':>4} {'Trunc':>5} {'R@1':>7} {'R@5':>7} {'R@10':>7} {'MRR':>7} | {'Correcto p50/p90':>17} {'Ajenas min':>11}")
    print("-" * 96)
    for clave, r in resultados.items():
        print(
            f"{clave:<10} {r['dimensiones']:>4} {r['docs_truncados']:>5} "
            f"{r['recall_1']:>6.1f}% {r['recall_5']:>6.1f}% {r['recall_10']:>6.1f}% {r['mrr']:>7.3f} | "
            f"{r['distancia_correcto_p50']:>8.3f}/{r['distancia_correcto_p90']:<8.3f} {r['distancia_ajenas_min']:>11.3f}"
        )
    print("=" * 96)
    print("Un buen umbral queda por encima de 'Correcto p90' y por debajo de 'Ajenas min'.")


def main():
    parser = argparse.ArgumentParser(description="Compara modelos de embeddings contra el Ground Truth.")
    parser.add_argument("modelos", nargs="*", default=list(CATALOGO_MODELOS), choices=list(CATALOGO_MODELOS), help="Claves de los modelos a comparar")
    parser.add_argument("--ground-truth", default=GROUND_TRUTH, help="Ruta al JSON de consultas")
    parser.add_argument("--salida", help="Ruta opcional para guardar los resultados en JSON")
    args = parser.parse_args()

    with open(args.ground_truth, encoding="utf-8") as f:
        consultas = json.load(f)
    textos, archivos = cargar_datasets()
    print(f"Datasets indexados: {len(textos)} | Consultas: {len(consultas)}")

    resultados = {}
    for clave in args.modelos:
        print(f"Evaluando {clave}...", flush=True)
        resultados[clave] = evaluar_modelo(clave, textos, archivos, consultas)

    imprimir_tabla(resultados)

    if args.salida:
        os.makedirs(os.path.dirname(args.salida) or ".", exist_ok=True)
        with open(args.salida, "w", encoding="utf-8") as f:
            json.dump({
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "datasets_indexados": len(textos),
                "consultas": len(consultas),
                "resultados": resultados,
            }, f, ensure_ascii=False, indent=2)
        print(f"\nResultados guardados en {args.salida}")


if __name__ == "__main__":
    main()
