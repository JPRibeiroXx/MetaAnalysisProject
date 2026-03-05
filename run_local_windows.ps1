# Run the Streamlit GUI locally on Windows.
# Creates .venv if needed, installs deps, then starts app.py

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

if (-not (Test-Path ".venv")) {
    Write-Host "[setup] Creating Python virtual environment (.venv)..."
    python -m venv .venv
}

# Activate venv
. ".venv\Scripts\Activate.ps1"

Write-Host "[setup] Installing / updating dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

Write-Host "[run] Launching Streamlit app at http://localhost:8501 ..."
streamlit run app.py
