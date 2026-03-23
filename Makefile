# ============================================================================
# Resume Intelligence V2 — Makefile
# ============================================================================
# Usage:
#   make install          Install all dependencies (prod + dev)
#   make test             Run ALL tests (unit + integration)
#   make test-unit        Run unit tests only
#   make test-integration Run integration tests only
#   make test-verbose     Run all tests with verbose output
#   make test-frontend    Run Vitest component unit tests
#   make test-e2e         Run Playwright E2E tests (requires running app)
#   make lint             Run Python linter (ruff)
#   make build            Build the React frontend
#   make dev              Start backend + frontend dev servers
#   make synth-data       Generate synthetic test data (files only, no DB)
#   make demo             Populate DB with 300 resumes + 100 jobs for demo. LOCALES="uk=18,eu=10"
#   make demo-reset       Wipe all demo data then reload with specified counts
#   make demo-wipe        Wipe all demo data (resumes + JDs, preserves non-demo)
#   make demo-wipe-all    Full DB wipe (all users) + reload fresh demo data
#   make clean            Remove generated artifacts
#   make help             Show this help
# ============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Detect Python
PYTHON := $(shell \
  if [ -f "$(CURDIR)/.venv/bin/python3" ]; then \
    echo "$(CURDIR)/.venv/bin/python3"; \
  else \
    command -v python3 2>/dev/null || command -v python 2>/dev/null; \
  fi)
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
NPM := npm

# Directories
PROJECT_ROOT := $(shell pwd)
BACKEND_DIR := $(PROJECT_ROOT)/backend
FRONTEND_DIR := $(PROJECT_ROOT)/frontend
TESTS_DIR := $(PROJECT_ROOT)/tests

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
CYAN := \033[0;36m
NC := \033[0m  # No Color

.PHONY: help install install-dev install-frontend test test-unit test-integration \
        test-verbose test-frontend test-e2e lint build dev dev-backend dev-frontend synth-data demo demo-reset demo-wipe demo-wipe-all clean

# ── Help ────────────────────────────────────────────────────────────────────

help: ## Show available targets
	@echo ""
	@echo "$(CYAN)Resume Intelligence V2$(NC) — Build & Test"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ── Install ─────────────────────────────────────────────────────────────────

install: install-dev install-frontend ## Install all dependencies (Python + Node)

install-dev: ## Install Python dependencies (prod + dev/test)
	@echo "$(CYAN)Installing Python dependencies...$(NC)"
	$(PIP) install -r requirements-dev.txt --quiet
	@echo "$(GREEN)Python dependencies installed.$(NC)"

install-frontend: ## Install Node.js frontend dependencies
	@echo "$(CYAN)Installing frontend dependencies...$(NC)"
	cd "$(FRONTEND_DIR)" && $(NPM) install --silent
	@echo "$(GREEN)Frontend dependencies installed.$(NC)"

# ── Test ────────────────────────────────────────────────────────────────────

test: ## Run ALL tests (unit + integration + system)
	@echo "$(CYAN)Running all tests...$(NC)"
	$(PYTEST) $(TESTS_DIR) --tb=short -q
	@echo "$(GREEN)All tests complete.$(NC)"

test-unit: ## Run unit tests only
	@echo "$(CYAN)Running unit tests...$(NC)"
	$(PYTEST) $(TESTS_DIR)/unit --tb=short -q
	@echo ""

test-integration: ## Run integration + system tests only
	@echo "$(CYAN)Running integration tests...$(NC)"
	$(PYTEST) $(TESTS_DIR)/integration $(TESTS_DIR)/test_*.py --tb=short -q
	@echo ""

test-verbose: ## Run all tests with verbose output
	$(PYTEST) $(TESTS_DIR) -v --tb=long

test-frontend: ## Run Vitest component unit tests
	@echo "$(CYAN)Running frontend unit tests (Vitest)...$(NC)"
	cd "$(FRONTEND_DIR)" && $(NPM) test
	@echo "$(GREEN)Frontend unit tests complete.$(NC)"

test-e2e: ## Run Playwright E2E tests (requires running app: make dev)
	@echo "$(CYAN)Running Playwright E2E tests...$(NC)"
	@echo "$(YELLOW)NOTE: App must be running on http://localhost:5173 (make dev)$(NC)"
	cd "$(PROJECT_ROOT)" && npx playwright test
	@echo "$(GREEN)E2E tests complete.$(NC)"

# ── Lint ────────────────────────────────────────────────────────────────────

lint: ## Run Python linter (ruff)
	@echo "$(CYAN)Linting Python code...$(NC)"
	$(PYTHON) -m ruff check backend/ services/ tests/ --fix 2>/dev/null || \
		echo "$(YELLOW)ruff not installed. Run: pip install ruff$(NC)"

# ── Build ───────────────────────────────────────────────────────────────────

build: ## Build the React frontend for production
	@echo "$(CYAN)Building frontend...$(NC)"
	cd "$(FRONTEND_DIR)" && $(NPM) run build
	@echo "$(GREEN)Frontend built → $(FRONTEND_DIR)/dist/$(NC)"

# ── Dev Servers ─────────────────────────────────────────────────────────────

dev: ## Start backend + frontend dev servers (parallel)
	@echo "$(CYAN)Starting dev servers...$(NC)"
	@bash "$(PROJECT_ROOT)/scripts/start_dev.sh"

dev-backend: ## Start backend only (uvicorn --reload)
	cd "$(BACKEND_DIR)" && $(PYTHON) -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend only (vite dev)
	cd "$(FRONTEND_DIR)" && $(NPM) run dev

# ── Synthetic Data ──────────────────────────────────────────────────────────

synth-data: ## Generate synthetic test data (resumes + JDs)
	@echo "$(CYAN)Generating synthetic data...$(NC)"
	$(PYTHON) "$(PROJECT_ROOT)/scripts/generate_synthetic_data.py"
	@echo "$(GREEN)Synthetic data generated.$(NC)"

# ── Demo Data ────────────────────────────────────────────────────────────────
# Override counts:  make demo RESUMES=300 JDS=100 LOCALES="india=100,uk=18,eu=10"
RESUMES ?= 300
JDS     ?= 100
LOCALES ?=

# Convert LOCALES="india=100,uk=18" → --locale india=100 --locale uk=18
comma := ,
_LOCALE_FLAGS = $(if $(LOCALES),$(foreach pair,$(subst $(comma), ,$(LOCALES)),--locale $(pair)),)

demo: ## Populate DB with synthetic data. Override: make demo RESUMES=50 JDS=20 LOCALES="uk=18,eu=10"
	@echo "$(CYAN)Loading demo data into DB...$(NC)"
	@echo "$(YELLOW)Resumes: $(RESUMES)  |  JDs: $(JDS)  |  Locales: $(LOCALES)$(NC)"
	$(PYTHON) "$(PROJECT_ROOT)/scripts/load_demo_data.py" --resumes $(RESUMES) --jds $(JDS) $(_LOCALE_FLAGS)

demo-reset: ## Wipe all demo data then reload with specified counts. Override: make demo-reset RESUMES=50 JDS=20 LOCALES="uk=18"
	@echo "$(YELLOW)Resetting demo data (RESUMES=$(RESUMES), JDS=$(JDS), LOCALES=$(LOCALES))...$(NC)"
	$(PYTHON) "$(PROJECT_ROOT)/scripts/load_demo_data.py" --reset --resumes $(RESUMES) --jds $(JDS) $(_LOCALE_FLAGS)

demo-wipe: ## Wipe all demo resumes + JDs from DB (preserves non-demo data)
	@echo "$(YELLOW)Wiping all demo data (resumes + JDs)...$(NC)"
	$(PYTHON) "$(PROJECT_ROOT)/scripts/load_demo_data.py" --wipe-demo

demo-wipe-all: ## Full DB wipe (all users, all tables) + reload fresh demo data
	@echo "$(YELLOW)Wiping entire DB and reloading demo dataset...$(NC)"
	$(PYTHON) "$(PROJECT_ROOT)/scripts/load_demo_data.py" --wipe --resumes $(RESUMES) --jds $(JDS) $(_LOCALE_FLAGS)

# ── Clean ───────────────────────────────────────────────────────────────────

clean: ## Remove generated artifacts (dist, caches, synth data)
	@echo "$(CYAN)Cleaning...$(NC)"
	rm -rf "$(FRONTEND_DIR)/dist"
	rm -rf "$(PROJECT_ROOT)/.pytest_cache"
	rm -rf "$(PROJECT_ROOT)/tests/__pycache__"
	rm -rf "$(PROJECT_ROOT)/tests/unit/__pycache__"
	rm -rf "$(PROJECT_ROOT)/tests/integration/__pycache__"
	find "$(PROJECT_ROOT)" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find "$(PROJECT_ROOT)" -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)Clean complete.$(NC)"
