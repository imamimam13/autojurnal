#!/usr/bin/env bash
set -e

echo "Menghentikan server AutoJurnal..."

PIDS=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    for p in $PIDS; do
        kill -9 "$p" 2>/dev/null || true
    done
fi

pkill -9 -f "uvicorn.*backend.main" 2>/dev/null || true
pkill -9 -f "backend.main:app" 2>/dev/null || true

if [ -f "$HOME/.autojurnal/server.pid" ]; then
    SAVED_PID=$(cat "$HOME/.autojurnal/server.pid" 2>/dev/null || true)
    if [ -n "$SAVED_PID" ]; then
        kill -9 "$SAVED_PID" 2>/dev/null || true
    fi
    rm -f "$HOME/.autojurnal/server.pid" 2>/dev/null || true
fi

sleep 0.3
RECHECK=$(lsof -ti :8000 2>/dev/null || true)
if [ -z "$RECHECK" ]; then
    echo "✅ Server AutoJurnal di port 8000 telah berhasil dihentikan."
else
    for p in $RECHECK; do
        kill -9 "$p" 2>/dev/null || true
    done
    echo "✅ Server AutoJurnal telah dihentikan secara paksa."
fi
