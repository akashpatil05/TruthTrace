#!/usr/bin/env bash
# backend/start.sh — Render production startup script
#
# 1. Seed the knowledge base if the vector store is empty (cold start)
# 2. Start the uvicorn server

set -e

echo "=== TruthTrace Backend Starting ==="
echo "Python: $(python --version)"
echo "Working dir: $(pwd)"

# ── Seed knowledge base on cold start ─────────────────────────────────────────
# The data/vector_store/ directory is committed to git with a seed index.
# If the index is missing or empty (e.g. first deploy with no git data),
# run a quick RSS ingest to bootstrap the knowledge base.

python - <<'EOF'
import sys, os
sys.path.insert(0, '.')
try:
    from app.services.retrieval import vector_store
    count = vector_store.count()
    print(f"[startup] Vector store has {count} chunks.")
    if count == 0:
        print("[startup] Empty store — running initial RSS ingest...")
        from ingest_pipeline import IngestionOrchestrator
        orch = IngestionOrchestrator()
        summary = orch.run_cycle(sources=['rss'], limit_per_cycle=50)
        orch.close()
        print(f"[startup] Seeded {summary.get('chunks_added', 0)} chunks from RSS.")
    else:
        print("[startup] Knowledge base already seeded. Ready.")
except Exception as e:
    print(f"[startup] Warning during seed check: {e}")
    print("[startup] Continuing anyway...")
EOF

# ── Start server ───────────────────────────────────────────────────────────────
echo "=== Starting uvicorn on port ${PORT:-8001} ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8001}" --workers 1
