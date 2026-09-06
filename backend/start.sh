#!/usr/bin/env bash
# backend/start.sh — Render production startup
set -e

echo "=== TruthTrace API Starting ==="
echo "Python  : $(python --version)"
echo "Port    : ${PORT:-8001}"
echo "WorkDir : $(pwd)"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8001}" \
    --workers 1
