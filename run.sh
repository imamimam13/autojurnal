#!/usr/bin/env bash
set -euo pipefail

echo "=== AutoJurnal ==="

# Set matplotlib temp directory for Mac/sandbox compatibility
export MPLCONFIGDIR=/tmp/matplotlib
export MPLBACKEND=Agg
mkdir -p /tmp/matplotlib

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing core dependencies..."
    pip install -q -r backend/requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "🚀 Starting AutoJurnal server..."
echo "👉 Open in your browser: http://localhost:8000"
echo ""

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
