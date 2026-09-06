"""
Embedding Service wrapping Sentence-Transformers behind a swappable interface.
"""

from abc import ABC, abstractmethod
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings


class BaseEmbeddingService(ABC):
    """Abstract interface for swappable embedding providers."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generate normalized embedding vectors for a list of texts."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        """Generate normalized embedding vector for a single query."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality."""
        pass


class SentenceTransformerEmbedding(BaseEmbeddingService):
    """
    Sentence-Transformers implementation.
    Defaults to all-MiniLM-L6-v2 (384-d), easily swappable to BAAI/bge-small-en-v1.5.
    """

    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._dim = settings.EMBEDDING_DIM

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-loaded model instance."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
            if hasattr(self._model, "get_embedding_dimension"):
                self._dim = self._model.get_embedding_dimension()
            else:
                self._dim = self._model.get_sentence_embedding_dimension()
        return self._model

    @property
    def dimension(self) -> int:
        if self._model is None:
            return self._dim
        if hasattr(self.model, "get_embedding_dimension"):
            return self.model.get_embedding_dimension()
        return self.model.get_sentence_embedding_dimension()

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a batch of texts.
        Returns float32 numpy array normalized to unit length for cosine similarity.
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return embeddings.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query text."""
        emb = self.embed_texts([text])
        return emb[0]


# Singleton default embedding service
embedding_service = SentenceTransformerEmbedding()
