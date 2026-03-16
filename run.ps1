# PowerShell script for project management on Windows
# Replicates functionality of the Unix Makefile

$ErrorActionPreference = "Stop"

$PROJECT_ROOT_DIR = (Get-Location).Path
$BACKEND_DIR = Join-Path $PROJECT_ROOT_DIR "backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT_DIR "frontend"
$TESTS_DIR = Join-Path $PROJECT_ROOT_DIR "tests"

# Detect Python inside venv if it exists, otherwise use system python
$PYTHON = "python"
$VENV_PYTHON = Join-Path $PROJECT_ROOT_DIR ".venv\Scripts\python.exe"
if (Test-Path $VENV_PYTHON) {
    $PYTHON = $VENV_PYTHON
}

function Show-Help {
    Write-Host ""
    Write-Host "Resume Intelligence V2 - Windows Management" -ForegroundColor Cyan
    Write-Host "----------------------------------------"
    Write-Host "  install           Install all dependencies (Python + Node)" -ForegroundColor Green
    Write-Host "  test              Run ALL tests (unit + integration)" -ForegroundColor Green
    Write-Host "  test-unit         Run unit tests only" -ForegroundColor Green
    Write-Host "  test-integration  Run integration tests only" -ForegroundColor Green
    Write-Host "  lint              Run Python linter (ruff)" -ForegroundColor Green
    Write-Host "  build             Build the React frontend" -ForegroundColor Green
    Write-Host "  dev               Start backend + frontend dev servers" -ForegroundColor Green
    Write-Host "  dev-backend       Start backend server only" -ForegroundColor Green
    Write-Host "  dev-frontend      Start frontend server only" -ForegroundColor Green
    Write-Host "  synth-data        Generate synthetic test data" -ForegroundColor Green
    Write-Host "  demo              Populate DB with demo data" -ForegroundColor Green
    Write-Host "  clean             Remove generated artifacts" -ForegroundColor Green
    Write-Host "  clean-db          Wipe the database tables and uploaded resumes" -ForegroundColor Green
    Write-Host "  help              Show this help" -ForegroundColor Green
    Write-Host ""
}

function Run-Install {
    Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
    if (-not (Test-Path (Join-Path $PROJECT_ROOT_DIR ".venv"))) {
        Write-Host "Creating Python virtual environment..."
        python -m venv .venv
    }
    & $PYTHON -m pip install -r requirements-dev.txt --quiet
    Write-Host "Python dependencies installed." -ForegroundColor Green

    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location $FRONTEND_DIR
    npm install --silent
    Pop-Location
    Write-Host "Frontend dependencies installed." -ForegroundColor Green
}

function Run-Test {
    param([string]$Target = "")
    Write-Host "Running tests..." -ForegroundColor Cyan
    if ($Target -eq "unit") {
        & $PYTHON -m pytest "$TESTS_DIR\unit" --tb=short -q
    } elseif ($Target -eq "integration") {
        & $PYTHON -m pytest "$TESTS_DIR\integration" --tb=short -q
    } else {
        & $PYTHON -m pytest "$TESTS_DIR\unit" "$TESTS_DIR\integration" --tb=short -q
    }
    Write-Host "Tests complete." -ForegroundColor Green
}

function Run-Lint {
    Write-Host "Linting Python code..." -ForegroundColor Cyan
    & $PYTHON -m ruff check backend/ services/ tests/ --fix
}

function Run-Build {
    Write-Host "Building frontend..." -ForegroundColor Cyan
    Push-Location $FRONTEND_DIR
    npm run build
    Pop-Location
    Write-Host "Frontend built." -ForegroundColor Green
}

function Run-Dev {
    Write-Host "Starting dev servers..." -ForegroundColor Cyan
    
    # Start Backend in a new window
    $BackendCmd = "cd '$BACKEND_DIR'; & '$PYTHON' -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $BackendCmd
    Write-Host "   - Backend starting on http://localhost:8000" -ForegroundColor Yellow

    # Start Frontend in current window
    Write-Host "   - Frontend starting on http://localhost:5173" -ForegroundColor Yellow
    Push-Location $FRONTEND_DIR
    npm run dev
    Pop-Location
}

function Run-SynthData {
    Write-Host "Generating synthetic data..." -ForegroundColor Cyan
    & $PYTHON (Join-Path $PROJECT_ROOT_DIR "scripts\generate_synthetic_data.py")
    Write-Host "Synthetic data generated." -ForegroundColor Green
}

function Run-Demo {
    param($Wipe = $false)
    $resumes = 300
    $jds = 100
    $india = 100
    $script = Join-Path $PROJECT_ROOT_DIR "scripts\load_demo_data.py"

    if ($Wipe) {
        Write-Host "Wiping and reloading demo data..." -ForegroundColor Yellow
        & $PYTHON $script --wipe --resumes $resumes --jds $jds --india $india
    } else {
        Write-Host "Loading demo data..." -ForegroundColor Cyan
        & $PYTHON $script --resumes $resumes --jds $jds --india $india
    }
}

function Run-Clean {
    Write-Host "Cleaning artifacts..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force (Join-Path $FRONTEND_DIR "dist") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force ".pytest_cache" -ErrorAction SilentlyContinue
    Get-ChildItem -Path $PROJECT_ROOT_DIR -Filter "__pycache__" -Recurse | Remove-Item -Recurse -Force
    Write-Host "Clean complete." -ForegroundColor Green
}

function Run-CleanDB {
    Write-Host "Wiping database and uploads..." -ForegroundColor Yellow
    & $PYTHON "scripts/wipe_database.py" --all --uploads --yes
    Write-Host "Database clean complete." -ForegroundColor Green
}

# Command line args handling
if ($args.Count -eq 0) {
    Show-Help
    exit
}

$cmd = $args[0]
switch ($cmd) {
    "help"             { Show-Help }
    "install"          { Run-Install }
    "test"             { Run-Test }
    "test-unit"        { Run-Test -Target "unit" }
    "test-integration" { Run-Test -Target "integration" }
    "lint"             { Run-Lint }
    "build"            { Run-Build }
    "dev"              { Run-Dev }
    "dev-backend"      { 
        Push-Location $BACKEND_DIR
        & $PYTHON -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
        Pop-Location
    }
    "dev-frontend"     { 
        Push-Location $FRONTEND_DIR
        npm run dev
        Pop-Location
    }
    "synth-data"       { Run-SynthData }
    "demo"             { Run-Demo }
    "demo-wipe"        { Run-Demo -Wipe $true }
    "clean"            { Run-Clean }
    "clean-db"         { Run-CleanDB }
    default            { 
        Write-Host "Unknown command: $cmd" -ForegroundColor Red
        Show-Help
    }
}

