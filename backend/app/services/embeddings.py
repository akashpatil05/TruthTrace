"""
Embedding Service wrapping FastEmbed (ONNX Runtime) with Sentence-Transformers fallback.

FastEmbed uses ~50MB RAM (vs ~450MB with PyTorch), fitting easily within
Render's 512MB free tier memory limit.
"""

from abc import ABC, abstractmethod
from typing import List, Union
import numpy as np

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


class FastEmbedEmbedding(BaseEmbeddingService):
    """
    Ultra-lightweight FastEmbed (ONNX Runtime) implementation.
    Consumes ~50MB RAM and runs 2-3x faster than full PyTorch.
    Compatible with existing FAISS index (384 dimensions).
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dim = settings.EMBEDDING_DIM

    @property
    def model(self):
        """Lazy-loaded FastEmbed model instance."""
        if self._model is None:
            try:
                from fastembed import TextEmbedding
                self._model = TextEmbedding(model_name=self.model_name)
            except ImportError:
                # Fallback to sentence_transformers if fastembed not installed
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a batch of texts.
        Returns float32 numpy array normalized to unit length for cosine similarity.
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        # Check if using FastEmbed (has embed method returning generator)
        if hasattr(self.model, "embed"):
            vectors = list(self.model.embed(texts))
            arr = np.array(vectors, dtype=np.float32)
            # Ensure L2 unit normalization
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return (arr / norms).astype(np.float32)

        # Fallback path for SentenceTransformer
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


# Backwards compatibility alias
SentenceTransformerEmbedding = FastEmbedEmbedding

# Singleton default embedding service
embedding_service = FastEmbedEmbedding()
