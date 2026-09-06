# Este archivo contiene la logica para generar embeddings de texto usando el modelo de sentence_transformers

from sentence_transformers import SentenceTransformer # Importamos sentence_transformers para poder usar el modelo de embeddings

modelo = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2') # Cargamos el modelo de embeddings multilingue de sentence_transformers

def generar_embedding(texto: str): # Esta funcion recibe un texto y lo devuelve en un vector matematico (embedding)
    return modelo.encode(texto).tolist()