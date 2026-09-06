"""
Document Ingestion & Preprocessing Service.

Handles text cleaning, HTML stripping, unicode normalization,
deterministic document deduplication hashing, and token-aware semantic chunking.
"""

import re
import html
import unicodedata
import hashlib
from typing import List, Tuple
import tiktoken

from app.config import settings
from app.models.schemas import (
    DocumentIngestRequest,
    DocumentChunk,
    DocumentResponse,
    DocumentMetadata,
)

# Initialize tokenizer (cl100k_base is the standard vocabulary for modern embeddings/LLMs)
try:
    _tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    _tokenizer = None


class DocumentPreprocessor:
    """Preprocesses raw documents: cleaning, deduplication hashing, and chunking."""

    def __init__(
        self,
        min_tokens: int = settings.CHUNK_MIN_TOKENS,
        target_tokens: int = settings.CHUNK_TARGET_TOKENS,
        max_tokens: int = settings.CHUNK_MAX_TOKENS,
        overlap_tokens: int = settings.CHUNK_OVERLAP_TOKENS,
    ):
        self.min_tokens = min_tokens
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    @staticmethod
    def count_tokens(text: str) -> int:
        """Count tokens accurately using tiktoken, falling back to whitespace estimation."""
        if _tokenizer:
            return len(_tokenizer.encode(text, disallowed_special=()))
        # Fallback heuristic: 1 token ~ 0.75 words
        return max(1, int(len(text.split()) * 1.33))

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """
        Clean and normalize raw text:
        - Strip HTML/XML tags and scripts
        - Unescape HTML entities (&amp; -> &)
        - Normalize unicode (NFKC)
        - Collapse excessive whitespace and line breaks
        """
        if not raw_text:
            return ""

        # Remove script and style blocks
        text = re.sub(r"<(script|style).*?>.*?</\1>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
        # Strip all HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Unescape HTML entities
        text = html.unescape(text)
        # Unicode normalization (NFKC decomposes compatibility chars and recomposes canonically)
        text = unicodedata.normalize("NFKC", text)
        # Remove non-printable control characters except newline and tab
        text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or unicodedata.category(ch)[0] != "C")
        # Replace multiple spaces/tabs with a single space
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse 3+ newlines to double newline (paragraph boundary)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()

    @staticmethod
    def generate_document_id(title: str, content: str, source: str) -> str:
        """
        Generate deterministic SHA-256 hash representing the document.
        Ensures identical documents produce the same ID for deduplication.
        """
        canonical_str = f"{title.strip().lower()}|{source.strip().lower()}|{content.strip()}"
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """Split text into sentences while preserving sentence delimiters."""
        # Split on sentence terminals followed by whitespace or newline
        sentence_pattern = r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])"
        paragraphs = text.split("\n\n")
        sentences = []
        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue
            parts = re.split(sentence_pattern, p_clean)
            for part in parts:
                part_strip = part.strip()
                if part_strip:
                    sentences.append(part_strip)
        return sentences

    def chunk_document(self, doc_id: str, cleaned_text: str, metadata: DocumentMetadata) -> List[DocumentChunk]:
        """
        Chunk document text into ~300-800 token sections with sentence-boundary preservation
        and sliding overlap.
        """
        total_tokens = self.count_tokens(cleaned_text)

        # If the whole document fits within max_tokens, keep as single chunk
        if total_tokens <= self.max_tokens:
            return [
                DocumentChunk(
                    chunk_id=f"{doc_id}_c0",
                    document_id=doc_id,
                    chunk_index=0,
                    text=cleaned_text,
                    token_count=total_tokens,
                    title=metadata.title,
                    source=metadata.source,
                    url=metadata.url,
                    publication_date=metadata.publication_date,
                    category=metadata.category,
                    source_type=metadata.source_type,
                    reliability_level=metadata.reliability_level,
                )
            ]

        sentences = self._split_into_sentences(cleaned_text)
        if not sentences:
            # Fallback if sentence splitting fails (e.g. single long line)
            sentences = [cleaned_text]

        chunks: List[DocumentChunk] = []
        current_sentences: List[str] = []
        current_tokens = 0
        chunk_idx = 0

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            # If a single sentence is abnormally large (> max_tokens), split it by words
            if sentence_tokens > self.max_tokens:
                words = sentence.split()
                sub_sentence = ""
                for word in words:
                    test_sub = f"{sub_sentence} {word}".strip()
                    if self.count_tokens(test_sub) > self.target_tokens and sub_sentence:
                        current_sentences.append(sub_sentence)
                        chunk_text = " ".join(current_sentences)
                        chunks.append(
                            DocumentChunk(
                                chunk_id=f"{doc_id}_c{chunk_idx}",
                                document_id=doc_id,
                                chunk_index=chunk_idx,
                                text=chunk_text,
                                token_count=self.count_tokens(chunk_text),
                                title=metadata.title,
                                source=metadata.source,
                                url=metadata.url,
                                publication_date=metadata.publication_date,
                                category=metadata.category,
                                source_type=metadata.source_type,
                                reliability_level=metadata.reliability_level,
                            )
                        )
                        chunk_idx += 1
                        current_sentences = []
                        sub_sentence = word
                    else:
                        sub_sentence = test_sub
                if sub_sentence:
                    current_sentences.append(sub_sentence)
                current_tokens = sum(self.count_tokens(s) for s in current_sentences)
                continue

            # Check if adding this sentence exceeds target_tokens
            if current_tokens + sentence_tokens > self.target_tokens and current_tokens >= self.min_tokens:
                # Emit current chunk
                chunk_text = " ".join(current_sentences)
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{doc_id}_c{chunk_idx}",
                        document_id=doc_id,
                        chunk_index=chunk_idx,
                        text=chunk_text,
                        token_count=self.count_tokens(chunk_text),
                        title=metadata.title,
                        source=metadata.source,
                        url=metadata.url,
                        publication_date=metadata.publication_date,
                        category=metadata.category,
                        source_type=metadata.source_type,
                        reliability_level=metadata.reliability_level,
                    )
                )
                chunk_idx += 1

                # Sliding overlap: keep trailing sentences totaling ~overlap_tokens
                overlap_sentences: List[str] = []
                overlap_tokens_accum = 0
                for s in reversed(current_sentences):
                    s_tok = self.count_tokens(s)
                    if overlap_tokens_accum + s_tok <= self.overlap_tokens:
                        overlap_sentences.insert(0, s)
                        overlap_tokens_accum += s_tok
                    else:
                        break

                current_sentences = overlap_sentences + [sentence]
                current_tokens = sum(self.count_tokens(s) for s in current_sentences)
            else:
                current_sentences.append(sentence)
                current_tokens += sentence_tokens

        # Emit remaining sentences as final chunk
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            final_token_count = self.count_tokens(chunk_text)

            # If the last chunk is very small (< min_tokens) and we already have prior chunks,
            # merge it into the previous chunk if total doesn't exceed max_tokens
            if final_token_count < self.min_tokens and chunks:
                prev = chunks[-1]
                merged_text = f"{prev.text} {chunk_text}"
                merged_tokens = self.count_tokens(merged_text)
                if merged_tokens <= self.max_tokens:
                    chunks[-1] = DocumentChunk(
                        chunk_id=prev.chunk_id,
                        document_id=prev.document_id,
                        chunk_index=prev.chunk_index,
                        text=merged_text,
                        token_count=merged_tokens,
                        title=metadata.title,
                        source=metadata.source,
                        url=metadata.url,
                        publication_date=metadata.publication_date,
                        category=metadata.category,
                        source_type=metadata.source_type,
                        reliability_level=metadata.reliability_level,
                    )
                else:
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{doc_id}_c{chunk_idx}",
                            document_id=doc_id,
                            chunk_index=chunk_idx,
                            text=chunk_text,
                            token_count=final_token_count,
                            title=metadata.title,
                            source=metadata.source,
                            url=metadata.url,
                            publication_date=metadata.publication_date,
                            category=metadata.category,
                            source_type=metadata.source_type,
                            reliability_level=metadata.reliability_level,
                        )
                    )
            else:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{doc_id}_c{chunk_idx}",
                        document_id=doc_id,
                        chunk_index=chunk_idx,
                        text=chunk_text,
                        token_count=final_token_count,
                        title=metadata.title,
                        source=metadata.source,
                        url=metadata.url,
                        publication_date=metadata.publication_date,
                        category=metadata.category,
                        source_type=metadata.source_type,
                        reliability_level=metadata.reliability_level,
                    )
                )

        return chunks

    def process_document(self, req: DocumentIngestRequest) -> DocumentResponse:
        """Complete pipeline: clean, deduplicate ID, and chunk."""
        cleaned_content = self.clean_text(req.content)
        doc_id = self.generate_document_id(req.title, cleaned_content, req.source)

        metadata = DocumentMetadata(
            document_id=doc_id,
            title=req.title.strip(),
            source=req.source.strip(),
            url=str(req.url),
            publication_date=req.publication_date,
            category=req.category,
            source_type=req.source_type,
            reliability_level=req.reliability_level,
        )

        chunks = self.chunk_document(doc_id, cleaned_content, metadata)
        total_tokens = sum(c.token_count for c in chunks)

        return DocumentResponse(
            document_id=doc_id,
            title=metadata.title,
            source=metadata.source,
            url=metadata.url,
            publication_date=metadata.publication_date,
            category=metadata.category,
            source_type=metadata.source_type,
            reliability_level=metadata.reliability_level,
            total_tokens=total_tokens,
            num_chunks=len(chunks),
            chunks=chunks,
        )


preprocessor = DocumentPreprocessor()
