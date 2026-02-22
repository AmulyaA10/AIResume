#!/bin/bash
set -e

# ==========================================
#   Resume Intelligence V2 — Dev Startup
# ==========================================
# Usage:  ./scripts/start_dev.sh
# Requires: Python 3.11+, Node.js 18+, npm

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKEND_PORT=8000
FRONTEND_PORT=5173
BACKEND_PID=""
FRONTEND_PID=""

# ---------- Helpers ----------

cleanup() {
    echo ""
    echo "[shutdown] Stopping services..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null && echo "   - Backend stopped."
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "   - Frontend stopped."
    exit 0
}

trap cleanup INT TERM

check_command() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: '$1' is not installed or not in PATH."
        exit 1
    fi
}

check_port() {
    if lsof -i :"$1" &>/dev/null; then
        echo "WARNING: Port $1 is already in use."
        echo "         Kill the process with:  lsof -ti :$1 | xargs kill -9"
        exit 1
    fi
}

# ---------- Pre-flight ----------

echo "=========================================="
echo "  Resume Intelligence V2 — Dev Startup"
echo "=========================================="
echo ""

echo "[1/5] Pre-flight checks..."
check_command python3
check_command node
check_command npm
check_port $BACKEND_PORT
check_port $FRONTEND_PORT
echo "   - All checks passed."

# ---------- Environment ----------

echo ""
echo "[2/5] Checking environment..."

if [ ! -f "$PROJECT_ROOT/backend/.env" ]; then
    echo "WARNING: backend/.env not found."
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        echo "   - Copying .env.example -> backend/.env (edit it with your keys)"
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/backend/.env"
    else
        echo "   - Create backend/.env with your OPEN_ROUTER_KEY."
    fi
fi
echo "   - Environment ready."

# ---------- Backend Setup ----------

echo ""
echo "[3/5] Setting up backend..."

cd "$PROJECT_ROOT"

if [ ! -d ".venv" ]; then
    echo "   - Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "   - Activating virtual environment..."
source .venv/bin/activate

echo "   - Installing/updating Python dependencies..."
pip install --upgrade pip -q 2>/dev/null
pip install -r requirements.txt -q 2>/dev/null
echo "   - Backend dependencies ready."

# ---------- Frontend Setup ----------

echo ""
echo "[4/5] Setting up frontend..."

cd "$PROJECT_ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "   - Installing Node.js dependencies..."
    npm install
else
    echo "   - Node modules present."
fi

# ---------- Start Services ----------

echo ""
echo "[5/5] Starting services..."

cd "$PROJECT_ROOT"

echo "   - Starting Backend on port $BACKEND_PORT..."
(cd backend && uvicorn main:app --reload --port "$BACKEND_PORT") &
BACKEND_PID=$!

echo "   - Starting Frontend on port $FRONTEND_PORT..."
(cd frontend && npm run dev -- --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

# Wait for services to boot
sleep 2

echo ""
echo "=========================================="
echo "  Services are running!"
echo ""
echo "  Frontend:  http://localhost:$FRONTEND_PORT"
echo "  Backend:   http://localhost:$BACKEND_PORT"
echo "  API Docs:  http://localhost:$BACKEND_PORT/docs"
echo ""
echo "  Press Ctrl+C to stop both services."
echo "=========================================="

wait
