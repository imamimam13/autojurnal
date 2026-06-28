#!/usr/bin/env bash
set -euo pipefail

echo "=== AutoJurnal ==="

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing core dependencies..."
pip install -q -r backend/requirements.txt
echo "Done. Install optional providers if needed: pip install -r backend/requirements-optional.txt"

echo ""
echo "Starting backend at http://localhost:8000"
echo "Open frontend at file://$(pwd)/frontend/index.html"
echo ""

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
