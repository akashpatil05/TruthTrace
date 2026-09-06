from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl

class SourceType(str, Enum):
    PEER_REVIEWED_JOURNAL = "peer_reviewed_journal"
    GOVERNMENT_AGENCY = "government_agency"
    NEWS_WIRE = "news_wire"
    MAINSTREAM_NEWS = "mainstream_news"
    FACT_CHECKER = "fact_checker"
    ACADEMIC_INSTITUTION = "academic_institution"
    OPINION_BLOG = "opinion_blog"
    UNVERIFIED = "unverified"

class ReliabilityLevel(str, Enum):
    VERY_HIGH = "VERY_HIGH"  # E.g. Nature, WHO, Reuters, AP
    HIGH = "HIGH"            # E.g. Major newspapers, CDC
    MEDIUM = "MEDIUM"        # E.g. Regional news, commentary
    LOW = "LOW"              # E.g. Unverified blogs, social commentary

class DocumentMetadata(BaseModel):
    document_id: str = Field(..., description="Unique deterministic hash or UUID for document")
    title: str = Field(..., description="Title or headline of the document")
    source: str = Field(..., description="Publishing organization or outlet")
    url: str = Field(..., description="Source URL where the document was published")
    publication_date: str = Field(..., description="Publication date in ISO format YYYY-MM-DD")
    category: str = Field(default="general", description="Domain category: health, science, politics, etc.")
    source_type: SourceType = Field(default=SourceType.NEWS_WIRE, description="Classification of the publishing entity")
    reliability_level: ReliabilityLevel = Field(default=ReliabilityLevel.HIGH, description="Assessed reliability level")

class DocumentIngestRequest(BaseModel):
    title: str = Field(..., description="Document headline or title")
    content: str = Field(..., min_length=10, description="Raw document text or HTML content")
    source: str = Field(..., description="Publisher name (e.g. WHO, Reuters, Nature)")
    url: str = Field(..., description="Web link or DOI to source material")
    publication_date: str = Field(..., description="Publication date (YYYY-MM-DD)")
    category: str = Field(default="general", description="Subject category")
    source_type: SourceType = Field(default=SourceType.NEWS_WIRE)
    reliability_level: ReliabilityLevel = Field(default=ReliabilityLevel.HIGH)

class DocumentChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique chunk identifier e.g. docid_chunkindex")
    document_id: str = Field(..., description="Parent document identifier")
    chunk_index: int = Field(..., description="0-indexed position in document")
    text: str = Field(..., description="Cleaned text content of the chunk")
    token_count: int = Field(..., description="Accurate token count of this chunk")
    # Inherited metadata for self-contained vector search
    title: str
    source: str
    url: str
    publication_date: str
    category: str
    source_type: SourceType
    reliability_level: ReliabilityLevel

class DocumentResponse(BaseModel):
    document_id: str
    title: str
    source: str
    url: str
    publication_date: str
    category: str
    source_type: SourceType
    reliability_level: ReliabilityLevel
    total_tokens: int
    num_chunks: int
    chunks: List[DocumentChunk] = Field(default_factory=list)

class VerdictEnum(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    MISLEADING = "MISLEADING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class EvidenceItem(BaseModel):
    source: str
    text: str
    url: str
    publication_date: str
    category: Optional[str] = "general"
    type: Optional[str] = "Primary Source"
    reliability_level: Optional[ReliabilityLevel] = ReliabilityLevel.HIGH
    score: Optional[float] = None

class VerificationRequest(BaseModel):
    text: str = Field(..., min_length=3, description="The news claim, headline, or article to verify")
    news_only: bool = Field(
        default=False,
        description="If true, restrict evidence retrieval to news-category chunks only"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of evidence chunks to retrieve per query"
    )

class VerificationResponse(BaseModel):
    verdict: VerdictEnum
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str
    reasoning: List[str] = Field(default_factory=list)
    supporting_evidence: List[EvidenceItem] = Field(default_factory=list)
    contradicting_evidence: List[EvidenceItem] = Field(default_factory=list)
    total_evidence_analyzed: int = 0
    processing_time_ms: float = 0.0
    knowledge_base_freshness: Optional[str] = Field(
        default=None,
        description="Publication date of the most recent evidence article retrieved"
    )
    news_sources_used: int = Field(
        default=0,
        description="Number of distinct news sources represented in retrieved evidence"
    )
    llm_powered: bool = Field(
        default=False,
        description="True if Gemini LLM produced this verdict; False if heuristic fallback was used"
    )

class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Overall health status of backend service")
    app: str = Field(default="TruthTrace", description="Application name")
    version: str = Field(default="1.0.0", description="Backend service version")
