import json
from pathlib import Path
import pytest

from app.services.preprocessing import DocumentPreprocessor
from app.models.schemas import DocumentIngestRequest, SourceType, ReliabilityLevel

BASE_DIR = Path(__file__).resolve().parent.parent.parent

@pytest.fixture
def preprocessor():
    return DocumentPreprocessor(
        min_tokens=50,
        target_tokens=150,
        max_tokens=300,
        overlap_tokens=30,
    )

def test_clean_text_html_and_whitespace(preprocessor):
    raw = "<h1>Breaking News!</h1><p>Scientists &amp; researchers   found that &lt;hot&gt; water is wet.<script>alert('hack')</script></p>\n\n\n\nNext line."
    cleaned = preprocessor.clean_text(raw)
    
    assert "<h1>" not in cleaned
    assert "<script>" not in cleaned
    assert "alert" not in cleaned
    assert "Scientists & researchers found that <hot> water is wet." in cleaned
    assert "\n\n\n" not in cleaned
    assert "Next line." in cleaned

def test_generate_document_id_deterministic(preprocessor):
    title = "Cancer and Coffee Study"
    content = "Drinking coffee does not prevent cancer."
    source = "World Health Organization"
    
    id1 = preprocessor.generate_document_id(title, content, source)
    id2 = preprocessor.generate_document_id(title, content, source)
    assert id1 == id2
    assert len(id1) == 16
    
    # Slight variation produces different ID
    id3 = preprocessor.generate_document_id(title, content + " Additional note.", source)
    assert id1 != id3

def test_chunking_short_document(preprocessor):
    req = DocumentIngestRequest(
        title="Short News Brief",
        content="This is a brief announcement about solar panel installations across universities.",
        source="Reuters",
        url="https://reuters.com/news/123",
        publication_date="2024-01-10",
        category="energy",
        source_type=SourceType.NEWS_WIRE,
        reliability_level=ReliabilityLevel.HIGH,
    )
    res = preprocessor.process_document(req)
    assert res.num_chunks == 1
    assert res.chunks[0].chunk_index == 0
    assert res.chunks[0].source == "Reuters"
    assert res.chunks[0].document_id == res.document_id

def test_chunking_long_document(preprocessor):
    # Construct a long text with multiple sentences
    sentences = [
        f"Sentence number {i} provides detailed factual background regarding public health surveillance and epidemiological evidence."
        for i in range(50)
    ]
    long_content = " ".join(sentences)
    
    req = DocumentIngestRequest(
        title="Epidemiological Survey 2024",
        content=long_content,
        source="CDC",
        url="https://cdc.gov/survey",
        publication_date="2024-02-01",
        category="health",
        source_type=SourceType.GOVERNMENT_AGENCY,
        reliability_level=ReliabilityLevel.VERY_HIGH,
    )
    res = preprocessor.process_document(req)
    assert res.num_chunks > 1
    for chunk in res.chunks:
        assert chunk.token_count <= 300
        assert chunk.document_id == res.document_id
        assert chunk.title == "Epidemiological Survey 2024"
        assert chunk.source_type == SourceType.GOVERNMENT_AGENCY

def test_process_sample_raw_files(preprocessor):
    cancer_doc_path = BASE_DIR / "data" / "raw" / "cancer_coffee_study.json"
    assert cancer_doc_path.exists(), f"Missing {cancer_doc_path}"
    
    with open(cancer_doc_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    req = DocumentIngestRequest(**data)
    res = preprocessor.process_document(req)
    
    assert res.title == data["title"]
    assert res.source == data["source"]
    assert res.num_chunks >= 1
    # Check that HTML was stripped in chunk text
    for c in res.chunks:
        assert "<p>" not in c.text
        assert "</p>" not in c.text
        assert "drinking coffee does not prevent cancer" in c.text.lower()
