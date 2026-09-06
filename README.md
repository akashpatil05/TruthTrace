# TruthTrace — RAG-Powered Fake News Detection & Verification System

TruthTrace is an evidence-grounded fake news detection and fact verification engine. Rather than relying on black-box classification, it retrieves factual evidence from authoritative sources, applies multi-query retrieval, and performs grounded LLM reasoning with strict JSON output schemas.

## Project Structure

```text
TruthTrace/
├── Frontend/                 # React frontend application
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── api/              # API Route Handlers (health, documents, verify)
│   │   ├── services/         # Business logic (preprocessing, embeddings, retrieval, llm, verification)
│   │   ├── models/           # Pydantic data schemas
│   │   ├── prompts/          # Verification and grounding prompt templates
│   │   ├── database/         # SQLite/SQLAlchemy models & migrations
│   │   ├── config.py         # App configuration & settings
│   │   └── main.py           # FastAPI entrypoint
│   ├── tests/                # Automated pytest suite
│   ├── requirements.txt      # Python dependencies
│   └── .env                  # Environment variables
├── data/
│   ├── raw/                  # Ingested evidence documents
│   ├── processed/            # Chunked and processed files
│   └── vector_store/         # ChromaDB persistence directory
└── evaluation/
    ├── test_cases.json       # Ground-truth evaluation dataset
    └── evaluate.py           # Metrics harness (Accuracy, F1, MRR, NDCG)
```

## Quick Start (Phase 0)

1. **Install Dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```

3. **Run Health Tests**:
   ```bash
   pytest
   ```

4. **Start Development Server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. **Verify Endpoint**:
   ```bash
   curl http://127.0.0.1:8000/api/health
   ```
