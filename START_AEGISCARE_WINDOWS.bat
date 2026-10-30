@echo off
setlocal
cd /d "%~dp0"
set PYVER=
py -3.12 --version >nul 2>nul
if not errorlevel 1 set PYVER=3.12
if "%PYVER%"=="" (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 set PYVER=3.11
)
if "%PYVER%"=="" (
  echo Python 3.12 or 3.11 is required. Your Python 3.12 installation is recommended.
  echo Check with: py -0p
  pause
  exit /b 1
)
if not exist .venv (
  py -%PYVER% -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check internet connection and Python version.
  pause
  exit /b 1
)
echo.
echo Starting AegisCare. Keep this window open.
echo Open http://127.0.0.1:8000 in your browser.
echo Health: http://127.0.0.1:8000/api/health
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
