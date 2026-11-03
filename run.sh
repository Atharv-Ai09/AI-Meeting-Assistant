#!/usr/bin/env bash
# Convenience launcher for Linux / macOS.
set -e
cd "$(dirname "$0")"

echo "=============================================================="
echo "  AI Meeting Assistant - Speech Recognition and Summarization"
echo "  Developed by Atharv Shetty | GTTC Belagavi | AI & ML"
echo "=============================================================="

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: Python 3.11 or 3.12 is required."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[1/3] Creating virtual environment with $PYTHON_BIN ..."
  "$PYTHON_BIN" -m venv .venv
  echo "[2/3] Installing dependencies (this can take several minutes) ..."
  .venv/bin/python -m pip install --upgrade pip setuptools wheel
  .venv/bin/python -m pip install -r requirements.txt
fi

[ -f .env ] || cp .env.example .env

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "WARNING: FFmpeg not found. Install it with: sudo apt install ffmpeg"
fi

echo "[3/3] Starting the application at http://127.0.0.1:5000 (Ctrl+C to stop)"
echo "The first transcription downloads AI models and may take several minutes."
exec .venv/bin/python app.py
