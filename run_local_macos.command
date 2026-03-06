#!/usr/bin/env bash
# Double-clickable launcher for macOS Finder.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Delegate to the main script (creates venv, installs deps, runs Streamlit)
./run_local_macos.sh
