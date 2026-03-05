@echo off
REM Run the Streamlit GUI locally on Windows (CMD).
REM Creates .venv if needed, installs deps, then starts app.py

setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0
cd /d "%ROOT%"

if not exist .venv (
    echo [setup] Creating Python virtual environment (.venv)...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [setup] Installing / updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [run] Launching Streamlit app at http://localhost:8501 ...
streamlit run app.py

endlocal
