import re
import threading
import hashlib
from typing import List, Optional

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

class ContentVectorizer:
    HASH_DIM = 128
    HASH_MODEL_NAME = "hash:blake2b-128"

    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        self.model_name = model_name
        self.device = "cpu"
        self.model = None
        self._load_failed = False
        self._load_lock = threading.Lock()

    def _clean_text(self, text: str) -> str:
        # cleaning text: lowercasing, removing HTML tags and punctuation
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'<.*?>', '', text)  # delete html
        text = re.sub(r'[^\w\s]', '', text) # delete punctuation
        return text.strip()

    def _load_model(self) -> None:
        if self.model is not None or self._load_failed:
            return
        with self._load_lock:
            if self.model is not None or self._load_failed:
                return
            try:
                import torch
                from sentence_transformers import SentenceTransformer

                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self.model = SentenceTransformer(self.model_name, device=self.device)
                logger.info("Vectorizer initialized on %s", self.device)
            except Exception as exc:
                self._load_failed = True
                logger.warning(
                    "SentenceTransformer unavailable. Falling back to hash embeddings: %s",
                    exc,
                )

    def use_hash_fallback(self) -> None:
        self.model = None
        self._load_failed = True

    @property
    def active_model_name(self) -> str:
        if self.model is None and self._load_failed:
            return self.HASH_MODEL_NAME
        if self.model is None:
            return f"{self.model_name}:pending"
        return self.model_name

    @staticmethod
    def _hash_embedding(text: str, dim: int = HASH_DIM) -> List[float]:
        vec = np.zeros(dim, dtype=float)
        if not text:
            return vec.tolist()

        for token in text.split():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            token_hash = int.from_bytes(digest[:8], byteorder="big", signed=False)
            index = token_hash % dim
            sign = -1.0 if (digest[8] % 2) else 1.0
            vec[index] += sign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def get_embedding(self, text: str) -> List[float]:
        # vector generating for single text
        cleaned = self._clean_text(text)
        if not cleaned:
            return []

        self._load_model()
        if self.model is None:
            return self._hash_embedding(cleaned)

        try:
            embedding = self.model.encode(cleaned, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as exc:
            logger.warning("Vectorization failed. Using hash fallback: %s", exc)
            return self._hash_embedding(cleaned)

    def get_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        # vector generating for batch of texts
        cleaned_texts = [self._clean_text(t) for t in texts if t]
        if not cleaned_texts:
            return []

        self._load_model()
        if self.model is None:
            return [self._hash_embedding(text) for text in cleaned_texts]

        try:
            embeddings = self.model.encode(
                cleaned_texts,
                batch_size=min(32, len(cleaned_texts)),
                show_progress_bar=False,
            )
            return embeddings.tolist()
        except Exception as exc:
            logger.warning("Batch vectorization failed. Using hash fallback: %s", exc)
            return [self._hash_embedding(text) for text in cleaned_texts]

_vectorizer: Optional[ContentVectorizer] = None
_vectorizer_lock = threading.Lock()


def get_vectorizer() -> ContentVectorizer:
    global _vectorizer
    if _vectorizer is None:
        with _vectorizer_lock:
            if _vectorizer is None:
                _vectorizer = ContentVectorizer()
    return _vectorizer
