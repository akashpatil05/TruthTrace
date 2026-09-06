"""
Script to seed the FAISS vector database from documents in data/raw/.
"""

import json
from pathlib import Path
from app.models.schemas import DocumentIngestRequest, SourceType, ReliabilityLevel
from app.services.preprocessing import preprocessor
from app.services.retrieval import vector_store

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

def seed_json_file(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    req = DocumentIngestRequest(**data)
    doc_res = preprocessor.process_document(req)
    count = vector_store.ingest_document(doc_res)
    print(f"Indexed {count} chunks from JSON: {req.title}")

def seed_txt_file(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.splitlines()
    meta = {}
    content_lines = []
    in_header = True

    for line in lines:
        if in_header and ":" in line and not line.startswith(" "):
            key, val = line.split(":", 1)
            meta[key.strip().lower()] = val.strip()
        elif in_header and not line.strip():
            in_header = False
        else:
            content_lines.append(line)

    req = DocumentIngestRequest(
        title=meta.get("title", file_path.stem),
        content="\n".join(content_lines),
        source=meta.get("source", "Unknown"),
        url=meta.get("url", "https://example.com"),
        publication_date=meta.get("date", "2024-01-01"),
        category=meta.get("category", "general"),
        source_type=SourceType(meta.get("source-type", "news_wire")),
        reliability_level=ReliabilityLevel(meta.get("reliability", "HIGH")),
    )
    doc_res = preprocessor.process_document(req)
    count = vector_store.ingest_document(doc_res)
    print(f"Indexed {count} chunks from TXT: {req.title}")

def main():
    print(f"Scanning raw documents in {RAW_DIR}...")
    for p in RAW_DIR.glob("*.*"):
        if p.suffix.lower() == ".json":
            seed_json_file(p)
        elif p.suffix.lower() == ".txt":
            seed_txt_file(p)

    print(f"\nVector Store Status:")
    print(f"- Total indexed chunks: {vector_store.count()}")
    print(f"- Total documents: {len(vector_store.list_documents())}")

if __name__ == "__main__":
    main()
