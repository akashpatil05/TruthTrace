import json
import shutil
from pathlib import Path
import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.embeddings import embedding_service
from app.services.retrieval import FAISSVectorStore, vector_store
from app.models.schemas import DocumentIngestRequest, SourceType, ReliabilityLevel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_test_vector_store(tmp_path, monkeypatch):
    """Ensure a clean, isolated vector store directory for each test run."""
    test_store_dir = tmp_path / "vector_store"
    test_store_dir.mkdir(parents=True, exist_ok=True)
    
    # Create an isolated store instance
    isolated_store = FAISSVectorStore(store_dir=test_store_dir, embed_service=embedding_service)
    
    # Patch global vector_store used by routes and retrieval
    monkeypatch.setattr("app.services.retrieval.vector_store", isolated_store)
    monkeypatch.setattr("app.api.documents.vector_store", isolated_store)
    
    yield isolated_store

def test_embedding_dimensions_and_normalization():
    texts = ["TruthTrace checks factual claims against high authority sources.", "Coffee does not cure cancer."]
    embs = embedding_service.embed_texts(texts)
    
    assert embs.shape == (2, 384)
    # Check L2 normalization (norm should be ~1.0)
    for v in embs:
        norm = np.linalg.norm(v)
        assert pytest.approx(norm, rel=1e-3) == 1.0

def test_faiss_lifecycle_and_search(clean_test_vector_store):
    store = clean_test_vector_store
    
    req = DocumentIngestRequest(
        title="WHO Coffee Evaluation",
        content="The WHO confirmed that drinking coffee does not prevent cancer or cure oncological diseases.",
        source="World Health Organization",
        url="https://who.int/coffee",
        publication_date="2023-06-15",
        category="health",
        source_type=SourceType.PEER_REVIEWED_JOURNAL,
        reliability_level=ReliabilityLevel.VERY_HIGH,
    )
    
    from app.services.preprocessing import preprocessor
    doc_res = preprocessor.process_document(req)
    
    # Ingest into store
    indexed_count = store.ingest_document(doc_res)
    assert indexed_count >= 1
    assert store.count() == indexed_count
    
    # Semantic Search
    query_vec = embedding_service.embed_query("Can coffee completely prevent cancer?")
    results = store.search(query_vec, top_k=3)
    
    assert len(results) >= 1
    top_result = results[0]
    assert top_result.score > 0.4
    assert "coffee" in top_result.chunk.text.lower()
    assert top_result.chunk.source == "World Health Organization"
    
    # Delete document
    assert store.delete_document(doc_res.document_id) is True
    assert store.count() == 0

def test_documents_api_crud_endpoints(clean_test_vector_store):
    # 1. Post document
    raw_doc_path = BASE_DIR / "data" / "raw" / "cancer_coffee_study.json"
    with open(raw_doc_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
        
    res = client.post("/api/documents", json=payload)
    assert res.status_code == 201
    data = res.json()
    doc_id = data["document_id"]
    assert len(doc_id) > 0
    assert data["num_chunks"] >= 1
    
    # 2. List documents
    res_list = client.get("/api/documents")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total_documents"] == 1
    assert list_data["documents"][0]["document_id"] == doc_id
    assert list_data["documents"][0]["title"] == payload["title"]
    
    # 3. Delete document
    res_del = client.delete(f"/api/documents/{doc_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"
    
    # 4. Verify list is now empty
    res_list_after = client.get("/api/documents")
    assert res_list_after.json()["total_documents"] == 0
