import os
from sentence_transformers import SentenceTransformer
import numpy as np

_model_instance = None

def get_embedding_model():
    global _model_instance
    if _model_instance is None:
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        print(f"Loading embedding model: {model_name}")
        _model_instance = SentenceTransformer(model_name)
    return _model_instance

def generate_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        model = get_embedding_model()
        embeddings = model.encode(texts)
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        print(f"Embedding generation failed: {e}")
        return []
