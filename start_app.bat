@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo   Resume Intelligence - Setup & Start
echo ==========================================

REM --- Backend Setup ---
echo.
echo [1/4] Checking Backend Environment...
if not exist ".venv" (
    echo    - Creating Python virtual environment...
    python -m venv .venv
)

echo    - Activating Virtual Environment...
call .venv\Scripts\activate

echo    - Installing/Updating Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing python requirements.
    pause
    exit /b %errorlevel%
)

REM --- Frontend Setup ---
echo.
echo [2/4] Checking Frontend Environment...
cd frontend
if not exist "node_modules" (
    echo    - Installing Node.js dependencies...
    cmd /c "npm install"
    if %errorlevel% neq 0 (
        echo Error installing npm packages.
        pause
        exit /b %errorlevel%
    )
)
cd ..

REM --- Start Services ---
echo.
echo [3/4] Starting Services...
echo.
echo    - Starting Backend (Port 8000)...
start "ResumeAI Backend" cmd /k "call .venv\Scripts\activate && cd backend && uvicorn main:app --reload"

echo    - Starting Frontend (Port 5173)...
start "ResumeAI Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo [4/4] Done! Services are launching in new windows.
echo        Backend: http://localhost:8000/docs
echo        Frontend: http://localhost:5173
echo.
pause
