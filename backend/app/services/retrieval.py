"""
Vector Store and Retrieval Service using FAISS.

Implements FAISS IndexFlatIP (Cosine Similarity with normalized vectors)
with disk persistence in data/vector_store/ and document lifecycle management.
"""

from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import threading
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import faiss

from app.config import settings
from app.models.schemas import DocumentChunk, DocumentResponse, SourceType, ReliabilityLevel
from app.services.embeddings import BaseEmbeddingService, embedding_service


class SearchResult:
    def __init__(self, chunk: DocumentChunk, score: float):
        self.chunk = chunk
        self.score = score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk.chunk_id,
            "document_id": self.chunk.document_id,
            "score": round(float(self.score), 4),
            "text": self.chunk.text,
            "title": self.chunk.title,
            "source": self.chunk.source,
            "url": self.chunk.url,
            "publication_date": self.chunk.publication_date,
            "category": self.chunk.category,
            "source_type": self.chunk.source_type.value,
            "reliability_level": self.chunk.reliability_level.value,
        }


class BaseVectorStore(ABC):
    """Abstract interface for vector database implementations."""

    @abstractmethod
    def add_chunks(self, chunks: List[DocumentChunk], embeddings: np.ndarray) -> int:
        pass

    @abstractmethod
    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[SearchResult]:
        pass

    @abstractmethod
    def delete_document(self, document_id: str) -> bool:
        pass

    @abstractmethod
    def list_documents(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass


class FAISSVectorStore(BaseVectorStore):
    """
    FAISS-powered vector store supporting Cosine Similarity, persistence,
    and document lifecycle operations.
    """

    def __init__(
        self,
        store_dir: Path = settings.VECTOR_STORE_DIR,
        embed_service: BaseEmbeddingService = embedding_service,
    ):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_dir / settings.FAISS_INDEX_FILE
        self.metadata_path = self.store_dir / settings.FAISS_METADATA_FILE
        self.embed_service = embed_service
        self.lock = threading.Lock()

        self.dimension = self.embed_service.dimension
        self.index: Optional[faiss.Index] = None
        self.chunks: List[DocumentChunk] = []
        self._last_loaded_mtime: float = 0.0

        self._load_or_initialize()

    def reload(self):
        """Force reload of the FAISS index and metadata from disk."""
        self._load_or_initialize()

    def _check_auto_reload(self):
        """Check if vector store files on disk were modified by an external process and reload."""
        if self.metadata_path.exists():
            try:
                disk_mtime = self.metadata_path.stat().st_mtime
                if disk_mtime > self._last_loaded_mtime:
                    self._load_or_initialize()
            except Exception:
                pass

    def _load_or_initialize(self):
        """Load persisted FAISS index and metadata from disk if present."""
        with self.lock:
            if self.index_path.exists() and self.metadata_path.exists():
                try:
                    self.index = faiss.read_index(str(self.index_path))
                    with open(self.metadata_path, "r", encoding="utf-8") as f:
                        raw_chunks = json.load(f)
                    self.chunks = [DocumentChunk(**c) for c in raw_chunks]
                    self._last_loaded_mtime = self.metadata_path.stat().st_mtime
                    return
                except Exception as e:
                    print(f"Warning: Failed to load FAISS index ({e}). Rebuilding new index.")

            # Initialize fresh empty inner product index
            self.index = faiss.IndexFlatIP(self.dimension)
            self.chunks = []
            self._last_loaded_mtime = 0.0

    def save(self):
        """Persist index and metadata atomically to disk."""
        with self.lock:
            if self.index is not None:
                faiss.write_index(self.index, str(self.index_path))
                raw_chunks = [c.model_dump() for c in self.chunks]
                temp_meta = self.metadata_path.with_suffix(".tmp")
                with open(temp_meta, "w", encoding="utf-8") as f:
                    json.dump(raw_chunks, f, ensure_ascii=False, indent=2)
                if temp_meta.exists():
                    os.replace(temp_meta, self.metadata_path)
                if self.metadata_path.exists():
                    self._last_loaded_mtime = self.metadata_path.stat().st_mtime

    def add_chunks(self, chunks: List[DocumentChunk], embeddings: np.ndarray) -> int:
        """Add new chunks and their corresponding embedding vectors to FAISS."""
        if not chunks:
            return 0

        with self.lock:
            # Check for existing duplicate chunk IDs and filter
            existing_chunk_ids = {c.chunk_id for c in self.chunks}
            new_chunks = []
            new_vectors = []

            for i, chunk in enumerate(chunks):
                if chunk.chunk_id not in existing_chunk_ids:
                    new_chunks.append(chunk)
                    new_vectors.append(embeddings[i])

            if not new_chunks:
                return 0

            vectors_np = np.array(new_vectors, dtype=np.float32)
            self.index.add(vectors_np)
            self.chunks.extend(new_chunks)

        self.save()
        return len(new_chunks)

    def ingest_document(self, doc_response: DocumentResponse) -> int:
        """Embed and index all chunks of a processed document."""
        if not doc_response.chunks:
            return 0

        texts = [chunk.text for chunk in doc_response.chunks]
        embeddings = self.embed_service.embed_texts(texts)
        return self.add_chunks(doc_response.chunks, embeddings)

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[SearchResult]:
        """
        Search for top_k most similar chunks using cosine similarity.
        Query vector must be normalized to unit length.
        """
        self._check_auto_reload()
        with self.lock:
            if self.index is None or self.index.ntotal == 0:
                return []

            k = min(top_k, self.index.ntotal)
            if query_vector.ndim == 1:
                q = np.expand_dims(query_vector.astype(np.float32), axis=0)
            else:
                q = query_vector.astype(np.float32)

            scores, indices = self.index.search(q, k)
            results: List[SearchResult] = []

            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(self.chunks):
                    results.append(SearchResult(chunk=self.chunks[idx], score=float(score)))

            return results

    def delete_document(self, document_id: str) -> bool:
        """
        Remove all chunks associated with a document_id and rebuild index.
        """
        with self.lock:
            prior_count = len(self.chunks)
            remaining_chunks = [c for c in self.chunks if c.document_id != document_id]

            if len(remaining_chunks) == prior_count:
                return False  # Document was not present

            # Rebuild FAISS index from remaining chunks
            new_index = faiss.IndexFlatIP(self.dimension)
            if remaining_chunks:
                texts = [c.text for c in remaining_chunks]
                new_vectors = self.embed_service.embed_texts(texts)
                new_index.add(new_vectors)

            self.index = new_index
            self.chunks = remaining_chunks

        self.save()
        return True

    def list_documents(
        self,
        category: Optional[str] = None,
        reliability_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List distinct indexed documents with summary metadata.

        Args:
            category: If set, only return documents matching this category (e.g. 'news', 'science').
            reliability_level: If set, only return documents at this reliability level.
        """
        self._check_auto_reload()
        with self.lock:
            docs: Dict[str, Dict[str, Any]] = {}
            for chunk in self.chunks:
                # Apply optional filters
                if category and chunk.category != category:
                    continue
                if reliability_level and chunk.reliability_level.value != reliability_level:
                    continue

                doc_id = chunk.document_id
                if doc_id not in docs:
                    docs[doc_id] = {
                        "document_id": doc_id,
                        "title": chunk.title,
                        "source": chunk.source,
                        "url": chunk.url,
                        "publication_date": chunk.publication_date,
                        "category": chunk.category,
                        "source_type": chunk.source_type.value,
                        "reliability_level": chunk.reliability_level.value,
                        "num_chunks": 0,
                        "total_tokens": 0,
                    }
                docs[doc_id]["num_chunks"] += 1
                docs[doc_id]["total_tokens"] += chunk.token_count

            return list(docs.values())

    def count(self) -> int:
        """Total number of indexed chunks."""
        self._check_auto_reload()
        with self.lock:
            return self.index.ntotal if self.index else 0

    def get_stats(self) -> Dict[str, Any]:
        """Return comprehensive statistics about the vector store."""
        self._check_auto_reload()
        with self.lock:
            if not self.chunks:
                return {
                    "total_chunks": 0,
                    "total_documents": 0,
                    "categories": {},
                    "reliability_breakdown": {},
                    "source_types": {},
                    "newest_article_date": None,
                    "oldest_article_date": None,
                    "sources": [],
                }

            categories: Dict[str, int] = {}
            reliability_breakdown: Dict[str, int] = {}
            source_types: Dict[str, int] = {}
            sources: set = set()
            dates: List[str] = []

            for chunk in self.chunks:
                cat = chunk.category or "general"
                categories[cat] = categories.get(cat, 0) + 1

                rel = chunk.reliability_level.value
                reliability_breakdown[rel] = reliability_breakdown.get(rel, 0) + 1

                st = chunk.source_type.value
                source_types[st] = source_types.get(st, 0) + 1

                sources.add(chunk.source)

                if chunk.publication_date:
                    dates.append(chunk.publication_date)

            dates_sorted = sorted(set(dates)) if dates else []

            doc_ids = {c.document_id for c in self.chunks}

            return {
                "total_chunks": len(self.chunks),
                "total_documents": len(doc_ids),
                "categories": categories,
                "reliability_breakdown": reliability_breakdown,
                "source_types": source_types,
                "newest_article_date": dates_sorted[-1] if dates_sorted else None,
                "oldest_article_date": dates_sorted[0] if dates_sorted else None,
                "unique_sources": len(sources),
                "sources": sorted(list(sources)),
            }

    def search_filtered(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search for similar chunks, optionally restricted to a specific category."""
        all_results = self.search(query_vector, top_k=top_k * 3)  # over-fetch then filter
        if category:
            all_results = [r for r in all_results if r.chunk.category == category]
        return all_results[:top_k]


# Global singleton instance of FAISS vector store
vector_store = FAISSVectorStore()
