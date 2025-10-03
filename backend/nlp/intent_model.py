import os
import json
import pickle
from typing import List, Tuple, Dict, Any

import numpy as np
from sentence_transformers import SentenceTransformer

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_PATH = os.path.join(DATA_DIR, "intent_examples.jsonl")
STORE_PATH = os.path.join(DATA_DIR, "intent_store.pkl")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _load_examples(path: str) -> Tuple[List[str], List[str]]:
    X, y = [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            X.append(obj["text"].lower())
            y.append(obj["label"])
    return X, y


def _encode_corpus(texts: List[str]) -> np.ndarray:
    model = SentenceTransformer(MODEL_NAME)
    embs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True).astype("float32")
    return embs


def _build_store() -> Dict[str, Any]:
    os.makedirs(DATA_DIR, exist_ok=True)
    X, y = _load_examples(DATA_PATH)
    embs = _encode_corpus(X)
    store = {"embeddings": embs, "labels": y, "texts": X, "model": MODEL_NAME}
    with open(STORE_PATH, "wb") as f:
        pickle.dump(store, f)
    return store


_store: Dict[str, Any] | None = None


def _get_store() -> Dict[str, Any]:
    global _store
    if _store is not None:
        return _store
    if os.path.exists(STORE_PATH):
        # Rebuild if examples are newer than the store
        try:
            store_mtime = os.path.getmtime(STORE_PATH)
            data_mtime = os.path.getmtime(DATA_PATH)
        except OSError:
            store_mtime = 0
            data_mtime = 1
        if data_mtime > store_mtime:
            _store = _build_store()
            return _store
        with open(STORE_PATH, "rb") as f:
            _store = pickle.load(f)
        return _store
    _store = _build_store()
    return _store


def predict_intent(text: str) -> Tuple[str, float]:
    """Nearest-neighbor intent over labeled examples using cosine similarity.
    Returns (label, confidence) where confidence is top similarity.
    """
    s = _get_store()
    model = SentenceTransformer(s.get("model", MODEL_NAME))
    q = model.encode([text.lower()], convert_to_numpy=True, normalize_embeddings=True).astype("float32")[0]
    corpus = s["embeddings"]  # (N, d)
    sims = (corpus @ q).astype("float32")  # cosine since normalized
    idx = int(np.argmax(sims))
    label = s["labels"][idx]
    conf = float(sims[idx])
    return label, conf
