@echo off
REM Run the Streamlit GUI locally on Windows (CMD).
REM Creates .venv if needed, installs deps, then starts app.py.
REM Keeps the window open so you can see any errors.

setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0
cd /d "%ROOT%"

echo [check] Looking for python on PATH...
where python >NUL 2>&1
if errorlevel 1 (
    echo.
    echo [error] Python was not found on PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo and make sure "Add python.exe to PATH" is checked.
    echo.
    pause
    exit /b 1
)

if not exist .venv (
    echo [setup] Creating Python virtual environment (.venv)...
    python -m venv .venv
)

if not exist .venv\Scripts\activate.bat (
    echo.
    echo [error] Could not find .venv\Scripts\activate.bat
    echo The virtual environment was not created correctly.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo [setup] Installing / updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [error] Dependency install failed.
    echo.
    pause
    exit /b 1
)

echo [run] Launching Streamlit app at http://localhost:8501 ...
echo (Press CTRL+C in this window to stop the app.)
echo.
streamlit run app.py

echo.
echo [done] Streamlit has exited. Press any key to close this window.
pause >NUL

endlocal
