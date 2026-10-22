# Este script mide la calidad del buscador semantico usando el Ground Truth de consultas reales.
# Consulta ChromaDB directamente (sin pasar por la API), asi no le afecta el rate limit ni el umbral de distancia,
# y permite comparar modelos de embeddings de forma limpia.
#
# Uso (desde cualquier carpeta):
#   python scripts/evaluate_model.py
#   python scripts/evaluate_model.py --salida eval/resultados/baseline.json

import os
import sys
import json
import argparse
from datetime import datetime

RAIZ_PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(RAIZ_PROYECTO)
os.chdir(RAIZ_PROYECTO) # ChromaDB usa la ruta relativa ./data/chroma_db; si se corre desde otra carpeta crearia una base vacia

from app.db_chroma import coleccion
from app.nlp_model import modelo

GROUND_TRUTH = "eval/ground_truth.json"
K_MAXIMO = 10 # Cuantos resultados pedimos a ChromaDB por consulta
UMBRAL_DISTANCIA = 0.60 # Debe coincidir con umbral_maximo en app/api/search.py
OBJETIVO_RECALL_5 = 85.0 # Meta de la planeacion: el dataset correcto aparece en el Top-5 en al menos 85% de las consultas


def cargar_ground_truth(ruta: str):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def validar_targets(consultas: list):
    # Si un target no existe en ChromaDB la consulta nunca podra acertar; avisamos para no confundirlo con un fallo del modelo
    datos = coleccion.get(include=["metadatas"])
    indexados = {meta.get("archivo_original") for meta in datos["metadatas"] if meta and meta.get("archivo_original")}
    if not indexados:
        sys.exit("ERROR: Ningun dataset en ChromaDB tiene 'archivo_original'. Ejecuta scripts/migrate_chroma.py primero.")

    faltantes = sorted({item["target"] for item in consultas} - indexados)
    if faltantes:
        print(f"AVISO: {len(faltantes)} targets del Ground Truth no estan indexados (sus consultas contaran como fallo):")
        for target in faltantes:
            print(f" - {target}")
        print()
    return len(datos["ids"])


def evaluar(consultas: list):
    textos = [item["consulta"] for item in consultas]
    vectores = modelo.encode(textos, batch_size=32).tolist() # Codificamos todas las consultas en lote, mucho mas rapido que una por una

    resultados = coleccion.query(query_embeddings=vectores, n_results=K_MAXIMO, include=["metadatas", "distances"])

    detalle = []
    for i, item in enumerate(consultas):
        metadatas = resultados["metadatas"][i]
        distancias = resultados["distances"][i]
        devueltos = [meta.get("archivo_original", "") for meta in metadatas]

        # Comparacion exacta: la posicion (1 = primer lugar) del dataset correcto, o None si no aparece en el Top-K
        posicion = devueltos.index(item["target"]) + 1 if item["target"] in devueltos else None

        detalle.append({
            "id": item["id"],
            "consulta": item["consulta"],
            "target": item["target"],
            "posicion": posicion,
            "distancia_target": round(distancias[posicion - 1], 4) if posicion else None,
            "top1": devueltos[0] if devueltos else None,
            "distancia_top1": round(distancias[0], 4) if distancias else None,
        })
    return detalle


def calcular_metricas(detalle: list):
    total = len(detalle)

    def recall(k):
        return 100 * sum(1 for d in detalle if d["posicion"] and d["posicion"] <= k) / total

    # Lo que realmente ve el ciudadano: el dataset correcto en el Top-5 y ademas dentro del umbral de la API
    visibles = sum(
        1 for d in detalle
        if d["posicion"] and d["posicion"] <= 5 and d["distancia_target"] <= UMBRAL_DISTANCIA
    )

    return {
        "total_consultas": total,
        "recall_1": round(recall(1), 2),
        "recall_5": round(recall(5), 2),
        "recall_10": round(recall(10), 2),
        "mrr_10": round(sum(1 / d["posicion"] for d in detalle if d["posicion"]) / total, 4), # Mean Reciprocal Rank: premia que el correcto salga lo mas arriba posible
        "recall_5_con_umbral": round(100 * visibles / total, 2),
    }


def imprimir_reporte(metricas: list, detalle: list, total_indexados: int):
    print("========================================")
    print("       RESULTADOS DE EVALUACION         ")
    print("========================================")
    print(f"Datasets indexados en ChromaDB: {total_indexados}")
    print(f"Consultas evaluadas:            {metricas['total_consultas']}")
    print(f"Recall@1:                       {metricas['recall_1']:.2f}%")
    print(f"Recall@5 (Top-5 Accuracy):      {metricas['recall_5']:.2f}%")
    print(f"Recall@10:                      {metricas['recall_10']:.2f}%")
    print(f"MRR@10:                         {metricas['mrr_10']:.4f}")
    print(f"Recall@5 con umbral {UMBRAL_DISTANCIA:.2f}:       {metricas['recall_5_con_umbral']:.2f}%")
    print("========================================\n")

    if metricas["recall_5"] >= OBJETIVO_RECALL_5:
        print(f"OBJETIVO CUMPLIDO: Recall@5 supera el {OBJETIVO_RECALL_5:.0f}% requerido en la planeacion.")
    else:
        print(f"Recall@5 esta por debajo del {OBJETIVO_RECALL_5:.0f}%. Revisa las descripciones de los datasets o el modelo de embeddings.")

    fallidos = [d for d in detalle if not d["posicion"] or d["posicion"] > 5]
    if fallidos:
        print(f"\nConsultas fuera del Top-5 ({len(fallidos)}):")
        for d in fallidos:
            posicion = f"posicion {d['posicion']}" if d["posicion"] else f"fuera del Top-{K_MAXIMO}"
            print(f" - [ID {d['id']}] '{d['consulta']}'")
            print(f"     Esperaba: {d['target']} ({posicion}) | Top-1: {d['top1']} (dist. {d['distancia_top1']})")

    filtrados = [d for d in detalle if d["posicion"] and d["posicion"] <= 5 and d["distancia_target"] > UMBRAL_DISTANCIA]
    if filtrados:
        print(f"\nAciertos en Top-5 que la API ocultaria por el umbral ({len(filtrados)}):")
        for d in filtrados:
            print(f" - [ID {d['id']}] '{d['consulta']}' -> {d['target']} (dist. {d['distancia_target']})")


def main():
    parser = argparse.ArgumentParser(description="Evalua el buscador semantico contra el Ground Truth.")
    parser.add_argument("--ground-truth", default=GROUND_TRUTH, help="Ruta al JSON de consultas")
    parser.add_argument("--salida", help="Ruta opcional para guardar metricas y detalle en JSON")
    args = parser.parse_args()

    consultas = cargar_ground_truth(args.ground_truth)
    total_indexados = validar_targets(consultas)
    detalle = evaluar(consultas)
    metricas = calcular_metricas(detalle)
    imprimir_reporte(metricas, detalle, total_indexados)

    if args.salida:
        os.makedirs(os.path.dirname(args.salida) or ".", exist_ok=True)
        with open(args.salida, "w", encoding="utf-8") as f:
            json.dump({
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "modelo": str(modelo.model_card_data.base_model or "desconocido"),
                "datasets_indexados": total_indexados,
                "umbral_distancia": UMBRAL_DISTANCIA,
                "metricas": metricas,
                "detalle": detalle,
            }, f, ensure_ascii=False, indent=2)
        print(f"\nResultados guardados en {args.salida}")


if __name__ == "__main__":
    main()
