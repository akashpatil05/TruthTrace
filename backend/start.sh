#!/usr/bin/env bash
# backend/start.sh — Render production startup
# Build succeeded: now just start uvicorn. The seeded FAISS index
# is committed to git (data/vector_store/) so no cold-seed needed.
set -e

echo "=== TruthTrace API Starting ==="
echo "Python  : $(python --version)"
echo "Port    : ${PORT:-8001}"
echo "WorkDir : $(pwd)"
echo "Data dir: $(ls -la ../data/vector_store/ 2>/dev/null || echo 'not found')"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8001}" \
    --workers 1 \
    --timeout-keep-alive 65
