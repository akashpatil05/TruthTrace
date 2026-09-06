"""
Document Ingestion & Management API Routes.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.models.schemas import DocumentIngestRequest, DocumentResponse
from app.services.preprocessing import preprocessor
from app.services.retrieval import vector_store

router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentListResponse(BaseModel):
    total_documents: int
    total_chunks: int
    documents: List[Dict[str, Any]]


class DocumentDeleteResponse(BaseModel):
    status: str = "deleted"
    document_id: str
    message: str


class NewsIngestRequest(BaseModel):
    source: str = Field(default="all", description="News source: all, newsapi, or rss")
    limit: int = Field(default=15, description="Number of articles per source")
    rss_sources: Optional[List[str]] = Field(default=None, description="Specific RSS sources to fetch")


class NewsIngestResponse(BaseModel):
    status: str = "success"
    newsapi_count: int = 0
    rss_count: int = 0
    total_ingested: int
    total_skipped: int
    message: str


class BatchIngestResponse(BaseModel):
    total_submitted: int
    total_indexed: int
    total_chunks: int
    failed: int
    errors: List[str] = Field(default_factory=list)


class KnowledgeBaseStats(BaseModel):
    total_chunks: int
    total_documents: int
    categories: Dict[str, int]
    reliability_breakdown: Dict[str, int]
    source_types: Dict[str, int]
    newest_article_date: Optional[str]
    oldest_article_date: Optional[str]
    unique_sources: int
    sources: List[str]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(payload: DocumentIngestRequest) -> DocumentResponse:
    """
    Ingest a trusted evidence document:
    1. Clean and normalize text / HTML
    2. Generate deterministic document ID
    3. Segment into token-aware semantic chunks with sliding overlap
    4. Compute Sentence-Transformer embeddings
    5. Persist into FAISS vector database
    """
    try:
        doc_response = preprocessor.process_document(payload)
        vector_store.ingest_document(doc_response)
        return doc_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest document: {str(e)}",
        )


@router.post("/batch", response_model=BatchIngestResponse, status_code=status.HTTP_200_OK)
async def batch_ingest_documents(payload: List[DocumentIngestRequest]) -> BatchIngestResponse:
    """
    Ingest a batch of documents in a single call — ideal for bulk loading thousands of articles.

    Each document is independently preprocessed, chunked, embedded, and indexed.
    Failed documents are reported in the 'errors' list; successful ones continue processing.
    """
    total_submitted = len(payload)
    total_indexed = 0
    total_chunks = 0
    errors: List[str] = []

    for doc_req in payload:
        try:
            doc_res = preprocessor.process_document(doc_req)
            chunks_added = vector_store.ingest_document(doc_res)
            if chunks_added > 0:
                total_indexed += 1
                total_chunks += chunks_added
        except Exception as exc:
            errors.append(f"{doc_req.title[:60]}: {str(exc)}")

    return BatchIngestResponse(
        total_submitted=total_submitted,
        total_indexed=total_indexed,
        total_chunks=total_chunks,
        failed=total_submitted - total_indexed,
        errors=errors,
    )


@router.get("/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats() -> KnowledgeBaseStats:
    """
    Return comprehensive statistics about the knowledge base:
    - Document and chunk counts
    - Category breakdown (news, science, health, etc.)
    - Reliability distribution
    - Newest and oldest article dates
    - List of all indexed sources
    """
    stats = vector_store.get_stats()
    return KnowledgeBaseStats(**stats)


@router.post("/ingest-news", response_model=NewsIngestResponse, status_code=status.HTTP_200_OK)
async def ingest_news(payload: NewsIngestRequest) -> NewsIngestResponse:
    """
    Fetch and ingest latest news from multiple sources into the knowledge base.

    Sources:
    - all: Fetch from both NewsAPI and RSS feeds
    - newsapi: Fact-checking related news from NewsAPI.org
    - rss: News from major outlets (BBC, Reuters, AP, NPR, Guardian, Al Jazeera)
    """
    try:
        from news_ingestion import NewsIngestPipeline

        pipeline = NewsIngestPipeline()

        if payload.source == "all":
            results = pipeline.ingest_all_sources(payload.limit)
            newsapi_count = results.get("newsapi", 0)
            rss_count = results.get("rss", 0)
        elif payload.source == "newsapi":
            newsapi_count = pipeline.ingest_from_newsapi(payload.limit)
            rss_count = 0
        elif payload.source == "rss":
            rss_count = pipeline.ingest_from_rss(payload.rss_sources, payload.limit)
            newsapi_count = 0
        else:
            raise ValueError(f"Unknown source: {payload.source}")

        total = newsapi_count + rss_count

        return NewsIngestResponse(
            status="success",
            newsapi_count=newsapi_count,
            rss_count=rss_count,
            total_ingested=total,
            total_skipped=pipeline.skipped_count,
            message=f"Successfully ingested {total} latest news articles from {payload.source}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest news: {str(e)}",
        )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    category: Optional[str] = Query(default=None, description="Filter by category (e.g. 'news', 'science', 'health')"),
    reliability_level: Optional[str] = Query(default=None, description="Filter by reliability level (VERY_HIGH, HIGH, MEDIUM, LOW)"),
) -> DocumentListResponse:
    """
    List all indexed documents stored in FAISS with chunk count and total tokens.
    Supports optional filtering by category and reliability level.
    """
    docs = vector_store.list_documents(category=category, reliability_level=reliability_level)
    return DocumentListResponse(
        total_documents=len(docs),
        total_chunks=vector_store.count(),
        documents=docs,
    )


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str) -> DocumentDeleteResponse:
    """
    Remove a document and all its chunks from the FAISS vector index.
    """
    deleted = vector_store.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found in index.",
        )
    return DocumentDeleteResponse(
        document_id=document_id,
        message=f"Document '{document_id}' and all associated chunks removed successfully.",
    )
