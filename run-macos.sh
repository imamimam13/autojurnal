#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== AutoJurnal (macOS Launcher) ==="

export MPLCONFIGDIR=/tmp/matplotlib
export MPLBACKEND=Agg
mkdir -p /tmp/matplotlib

if [ ! -d "venv" ]; then
    echo "Virtual environment belum ditemukan. Menjalankan instalasi..."
    ./install-macos.sh
fi

source venv/bin/activate

echo ""
echo "🚀 Starting AutoJurnal server..."
echo "👉 Open in your browser: http://localhost:8000"
echo ""

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
