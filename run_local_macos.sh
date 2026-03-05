#!/usr/bin/env bash
set -euo pipefail

# Run the Streamlit GUI locally on macOS / Linux.
# Creates .venv if needed, installs deps, then starts app.py

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d .venv ]; then
  echo "[setup] Creating Python virtual environment (.venv)..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "[setup] Installing / updating dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[run] Launching Streamlit app at http://localhost:8501 ..."
exec streamlit run app.py
