# Este archivo contiene la logica para generar embeddings de texto usando el modelo de sentence_transformers

from sentence_transformers import SentenceTransformer # Importamos sentence_transformers para poder usar el modelo de embeddings

# Modelo multilingue elegido con eval/experimentos/2026-10-21_comparacion_modelos.md (Recall@5: 95% vs 78% del anterior)
NOMBRE_MODELO = "intfloat/multilingual-e5-small"

# Los modelos e5 se entrenaron con estos prefijos: sin ellos el modelo rinde bastante peor
PREFIJO_CONSULTA = "query: " # Lo que escribe el ciudadano
PREFIJO_DOCUMENTO = "passage: " # Los textos de los datasets que se indexan

# Distancia coseno maxima para mostrar un resultado. Depende del modelo: e5 concentra las distancias entre ~0.1 y ~0.25,
# asi que si se cambia de modelo hay que recalibrarlo con scripts/evaluate_model.py
UMBRAL_DISTANCIA = 0.19

modelo = SentenceTransformer(NOMBRE_MODELO) # Se carga una sola vez al importar el modulo


def texto_para_indexar(titulo: str, descripcion: str, dependencia: str) -> str:
    # Unico formato del texto que se convierte en embedding; lo comparten el panel y scripts/migrate_chroma.py
    return f"{titulo}. {descripcion} Dependencia: {dependencia}"


def _codificar(textos: list, prefijo: str) -> list:
    vectores = modelo.encode([prefijo + t for t in textos], normalize_embeddings=True, batch_size=32)
    return vectores.tolist()


def generar_embedding_consulta(texto: str) -> list: # Convierte la busqueda de un ciudadano en un vector
    return _codificar([texto], PREFIJO_CONSULTA)[0]


def generar_embeddings_consultas(textos: list) -> list: # Version en lote, para evaluar muchas consultas a la vez
    return _codificar(textos, PREFIJO_CONSULTA)


def generar_embedding_documento(texto: str) -> list: # Convierte el texto de un dataset en un vector para indexarlo
    return _codificar([texto], PREFIJO_DOCUMENTO)[0]


def generar_embeddings_documentos(textos: list) -> list: # Version en lote, para indexar el catalogo completo
    return _codificar(textos, PREFIJO_DOCUMENTO)
