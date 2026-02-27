# Resume Intelligence V2

AI-powered resume screening, scoring, skill-gap analysis, and generation platform built with React, FastAPI, LangGraph, and LanceDB.

---

## Features

- **Resume Upload & Parsing** — Bulk upload PDF/DOCX resumes with automatic text extraction and vector embedding
- **AI-Powered Semantic Search** — Find the best-fit candidates using natural-language queries against a vector database
- **Quality Scoring** — LLM-driven resume quality analysis with detailed section-by-section feedback
- **Skill Gap Analysis** — Compare a resume against a job description to identify missing skills and experience
- **Auto Screening** — Automated candidate screening with configurable pass/fail thresholds
- **Resume Generation** — Generate professional resumes from profile descriptions using AI
- **LinkedIn Integration** — OAuth login + Selenium-based LinkedIn profile scraping and resume conversion
- **Dashboard & Analytics** — Activity tracking, screening history, and usage statistics

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite 7, Tailwind CSS 3 |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| AI Engine | LangGraph, LangChain, OpenAI (via OpenRouter) |
| Vector DB | LanceDB (PyArrow schema, 1536-dim embeddings) |
| Auth | Google OAuth, LinkedIn OAuth (mock fallback) |

---

## Project Structure

```
ResumeIntelligenceV2-main/
├── frontend/                     # React + Vite + TypeScript
│   └── src/
│       ├── features/             # Feature-based page modules
│       │   ├── auth/             # Login, OAuth callback
│       │   ├── dashboard/        # Dashboard, Job definitions
│       │   ├── resumes/          # Upload, Generator, LinkedIn scraper
│       │   ├── analysis/         # Quality scoring, Skill gap, Screening, Search
│       │   └── settings/         # User settings
│       ├── common/               # Shared UI components
│       ├── components/           # Layout, Sidebar
│       ├── context/              # AuthContext
│       └── api.ts                # Axios client + interceptors
│
├── backend/                      # FastAPI application
│   ├── main.py                   # Entry point (app factory)
│   └── app/
│       ├── __init__.py           # create_app() factory
│       ├── config.py             # Environment variables
│       ├── models.py             # Pydantic request/response models
│       ├── dependencies.py       # Auth dependency injection
│       ├── common/               # Shared route helpers
│       └── routes/
│           └── v1/               # API v1 route handlers
│
├── services/                     # AI + business logic
│   ├── agent_controller.py       # Graph orchestrator
│   ├── ai/                       # LangGraph workflow definitions
│   │   ├── common/               # Shared AI utilities (get_llm, parsers)
│   │   ├── resume_quality_graph.py
│   │   ├── skill_gap_graph.py
│   │   ├── screening_graph.py
│   │   ├── resume_generator_graph.py
│   │   └── linkedin_resume_graph.py
│   └── db/
│       └── lancedb_client.py     # Vector DB operations
│
├── tests/                        # Test files
├── scripts/                      # Developer tooling
├── legacy/                       # Frozen Streamlit app
└── Agent.md                      # Standards & conventions doc
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **OpenRouter API key** (for LLM and embeddings)

Optional:
- Google OAuth credentials (for Google login)
- LinkedIn OAuth credentials (for LinkedIn login)
- LinkedIn account credentials (for profile scraping)

---

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd ResumeIntelligenceV2-main
```

### 2. Configure environment variables

```bash
cp .env.example backend/.env
```

Edit `backend/.env` and add your API keys:

```env
OPEN_ROUTER_KEY=your_openrouter_api_key

# Optional — OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret

# Optional — LinkedIn scraper
LinkedinLogin=your_linkedin_email
LinkedinPassword=your_linkedin_password
```

### 3. Start the application

**Automated (macOS / Linux):**

```bash
./scripts/start_dev.sh
```

**Manual:**

```bash
# Terminal 1 — Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn main:app --reload

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

### 4. Access the application

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

---

## API Versioning

All API endpoints are versioned under `/api/v1/`:

```
POST /api/v1/auth/login
GET  /api/v1/dashboard/stats
POST /api/v1/resumes/upload
POST /api/v1/analyze/quality
POST /api/v1/analyze/skill-gap
POST /api/v1/analyze/screen
POST /api/v1/generate/resume
GET  /api/v1/search
POST /api/v1/linkedin/scrape
GET  /health
```

When breaking changes are introduced, a `v2` version will be created alongside `v1` to maintain backward compatibility.

---

## Development

### Adding a new feature

1. Create the LangGraph workflow in `services/ai/<feature>_graph.py`
2. Register the graph in `services/agent_controller.py`
3. Add Pydantic models in `backend/app/models.py`
4. Create route file in `backend/app/routes/v1/<domain>.py`
5. Register the router in `routes/v1/__init__.py` and `app/__init__.py`
6. Create the frontend page in `frontend/src/features/<domain>/`
7. Add the route in `App.tsx` and nav link in `Sidebar.tsx`

See `Agent.md` for detailed coding standards and conventions.

---

## License

This project is proprietary. All rights reserved.
