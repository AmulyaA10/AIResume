#!/bin/bash
set -e

echo "=========================================="
echo "  Resume Intelligence - Setup & Start"
echo "=========================================="

# Backend Setup
echo ""
echo "[1/4] Checking Backend Environment..."
if [ ! -d ".venv" ]; then
    echo "   - Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "   - Activating Virtual Environment..."
source .venv/bin/activate

echo "   - Installing/Updating Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Frontend Setup
echo ""
echo "[2/4] Checking Frontend Environment..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "   - Installing Node.js dependencies..."
    npm install
fi
cd ..

# Start Services
echo ""
echo "[3/4] Starting Services..."
echo "   - Starting Backend (Port 8000)..."
(cd backend && uvicorn main:app --reload) &
BACKEND_PID=$!

echo "   - Starting Frontend (Port 5173)..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "[4/4] Done! Services are running."
echo "       Backend:  http://localhost:8000/docs"
echo "       Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both services."

# Trap Ctrl+C to kill both processes
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
