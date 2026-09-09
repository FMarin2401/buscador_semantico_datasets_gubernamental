# Este archivo contiene la logica para guardar y buscar datasets en la base de datos ChromaDB

import chromadb
import logging

logger = logging.getLogger(__name__)
cliente = chromadb.PersistentClient(path="./data/chroma_db") # Al usar PersistentClient, los datos se guardan en el disco y se pueden recuperar despues de reiniciar la aplicacion

coleccion = cliente.get_or_create_collection( # Busca o crea una coleccion en la base de datos ChromaDB para guardar los datasets
    name="datasets_gobierno",
    metadata={"hnsw:space": "cosine"} # Usamos la similitud coseno para medir la distancia entre los embeddings de texto, lo que es adecuado para comparar vectores de alta dimensión
)

def buscar_similares(vector_busqueda: list, n_resultados: int): # Funcion para cada que un usuario haga una busqueda
    return coleccion.query(
        query_embeddings=[vector_busqueda], # Buscamos los embeddings mas similares al vector de busqueda del usuario
        n_results=n_resultados # Devolvemos los n_resultados mas similares al vector de busqueda
    )

def obtener_todos_datasets():
    return coleccion.get(include=["metadatas", "documents"]) # Extraer los documentos (títulos) y los metadatos (dependencia, fecha)


def guardar_datasets(ids: list, textos: list, embeddings: list, metadatas: list): 
    coleccion.add(
        ids=ids,
        documents=textos,
        embeddings=embeddings,
        metadatas=metadatas 
    )
