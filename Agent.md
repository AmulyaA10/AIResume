# Agent.md — Resume Intelligence V2

> **This file is the single source of truth for all AI agents and human developers.**
> Every code change — whether made by Claude, Copilot, Cursor, GPT, or a human — MUST
> comply with the standards below. Read this file in full before writing any code.

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Name** | Resume Intelligence V2 |
| **Purpose** | AI-powered resume screening, scoring, skill-gap analysis, and generation platform |
| **Frontend** | React 19 + TypeScript + Vite 7 + Tailwind CSS 3 |
| **Backend** | Python 3.11+ / FastAPI + Uvicorn |
| **AI Engine** | LangGraph + LangChain + OpenAI (via OpenRouter) |
| **Vector DB** | LanceDB (PyArrow schema, 1536-dim embeddings) |
| **Auth** | Google OAuth + LinkedIn OAuth (mock fallback) |
| **Package Mgmt** | npm (frontend), pip/requirements.txt (backend) |

---

## 2. Directory Structure

```
ResumeIntelligenceV2-main/
├── frontend/                        # React + Vite + TypeScript (UNCHANGED)
│   ├── src/
│   │   ├── pages/                   # One file per route (PascalCase.tsx)
│   │   ├── components/              # Layout.tsx, Sidebar.tsx, SettingsSidebar.tsx
│   │   ├── context/                 # AuthContext.tsx
│   │   ├── api.ts                   # Axios instance + interceptors
│   │   ├── App.tsx                  # Route definitions
│   │   └── main.tsx                 # Entry point
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── backend/                         # FastAPI application
│   ├── main.py                      # Entry point (7 lines — imports app factory)
│   ├── .env                         # Secrets (NEVER committed)
│   ├── data/                        # Runtime data
│   │   ├── raw_resumes/
│   │   └── lancedb/
│   └── app/                         # Application package
│       ├── __init__.py              # App factory: create_app() + sys.path setup
│       ├── config.py                # All env vars and constants
│       ├── models.py                # Pydantic request/response models
│       ├── dependencies.py          # get_current_user() and shared deps
│       └── routes/                  # One file per API domain
│           ├── __init__.py          # Exports all routers
│           ├── auth.py              # /api/auth/* (login, OAuth)
│           ├── resumes.py           # /api/resumes/* (upload, download)
│           ├── dashboard.py         # /api/dashboard/* (stats)
│           ├── search.py            # /api/search (semantic search)
│           ├── analyze.py           # /api/analyze/* (quality, gap, screen)
│           ├── generate.py          # /api/generate/* (resume gen, export)
│           ├── linkedin.py          # /api/linkedin/* (scrape)
│           ├── user.py              # /api/user/* (profile)
│           └── health.py            # /health
│
├── services/                        # AI + business logic (shared by backend + legacy)
│   ├── __init__.py
│   ├── agent_controller.py          # Orchestrator — dispatches to compiled graphs
│   ├── resume_parser.py             # Text extraction from PDF/DOCX
│   ├── export_service.py            # DOCX generation
│   ├── linkedin_scraper.py          # Selenium-based LinkedIn scraper
│   ├── ai/                          # LangGraph workflow definitions
│   │   ├── __init__.py
│   │   ├── resume_quality_graph.py  # Quality scoring graph
│   │   ├── skill_gap_graph.py       # Skill gap analysis graph
│   │   ├── screening_graph.py       # Auto-screening graph
│   │   ├── resume_generator_graph.py # Resume generation graph
│   │   ├── linkedin_resume_graph.py # LinkedIn-to-resume graph
│   │   └── langgraph_workflow.py    # Legacy base workflow (mock data)
│   └── db/
│       ├── __init__.py
│       └── lancedb_client.py        # Vector DB operations + schema
│
├── data/                            # Runtime data (gitignored uploads)
│   ├── raw_resumes/
│   └── lancedb/
│
├── tests/                           # Test files
│   ├── test_gemini.py
│   ├── test_semantic_search.py
│   ├── test_dynamic_config.py
│   └── check_db_state.py
│
├── scripts/                         # Developer tooling
│   ├── reindex_resumes.py
│   └── start_dev.sh                 # macOS/Linux startup script
│
├── legacy/                          # Frozen Streamlit interface (do NOT modify)
│   ├── app.py
│   ├── Pages/
│   └── components/
│
├── Wireframe/                       # UI prototype
│
├── .env.example                     # Onboarding template (no real secrets)
├── .gitignore                       # Comprehensive ignore rules
├── requirements.txt                 # Python dependencies
├── start_app.bat                    # Windows dev startup script
└── Agent.md                         # THIS FILE
```

### Rules for Structure

- **Do NOT create new top-level directories** without team discussion.
- **Do NOT move files between directories** without updating all imports.
- **Legacy code** (`legacy/`) is frozen. Do not modify it.
- New frontend pages go in `frontend/src/pages/`.
- New AI graphs go in `services/ai/` with the naming pattern `<feature>_graph.py`.
- New route files go in `backend/app/routes/`.
- New DB operations go in `services/db/lancedb_client.py` (extend, don't create new files).
- Pydantic models go in `backend/app/models.py`.
- Environment variables go in `backend/app/config.py`.

---

## 3. Naming Conventions

### Python

| What | Convention | Example |
|---|---|---|
| Files | `snake_case.py` | `resume_quality_graph.py` |
| Functions | `snake_case` | `build_screening_graph()` |
| Variables | `snake_case` | `resume_text`, `user_id` |
| Constants | `SCREAMING_SNAKE_CASE` | `UPLOAD_DIR`, `DB_PATH` |
| Classes (Pydantic) | `PascalCase` | `LoginRequest`, `AnalyzeRequest` |
| TypedDict States | `PascalCase` + `State` suffix | `ScreeningState`, `SkillGapState` |
| LangGraph agents | `snake_case` + `_agent` suffix | `screening_agent`, `resume_reader_agent` |
| LangGraph node IDs | short lowercase verbs | `"reader"`, `"score"`, `"screen"`, `"compare"` |
| Graph builders | `build_<name>_graph()` | `build_skill_gap_graph()` |
| Route files | `snake_case.py` by API domain | `auth.py`, `resumes.py`, `analyze.py` |

### TypeScript / React

| What | Convention | Example |
|---|---|---|
| Component files | `PascalCase.tsx` | `Dashboard.tsx`, `ResumeUpload.tsx` |
| Utility files | `camelCase.ts` | `api.ts` |
| Components | `PascalCase` (arrow functions) | `const Dashboard = () => {}` |
| Functions/vars | `camelCase` | `handleUpload`, `fetchStats` |
| Event handlers | `handle` prefix | `handleFileChange`, `handleSave` |
| Interfaces | `PascalCase` | `AuthContextType`, `User` |
| Type aliases | `PascalCase` | `type Persona = 'jobseeker' \| 'recruiter'` |
| CSS classes | Tailwind utility classes only | `className="bg-white p-6 rounded-xl"` |

---

## 4. Tech Stack — Do NOT Deviate

### Frontend (locked versions)

```
react: ^19.2.0
react-dom: ^19.2.0
react-router-dom: ^7.13.0
axios: ^1.13.5
tailwindcss: ^3.4.1
framer-motion: ^12.34.0
lucide-react: ^0.563.0
vite: ^7.3.1
typescript (via @types/react)
```

**Do NOT add**: Material UI, Chakra UI, Bootstrap, styled-components, Redux, Zustand,
or any other UI/state library. Use Tailwind for styling and React Context for state.

### Backend (locked dependencies)

```
fastapi
uvicorn
python-dotenv
python-multipart
pydantic
langgraph
langchain-openai
langchain-core
lancedb
pyarrow
pypdf
python-docx
selenium
webdriver-manager
google-generativeai
```

**Do NOT add**: Django, Flask, SQLAlchemy, Alembic, Celery, or any ORM.
LanceDB is the sole data store. Add new pip packages only with team approval.

---

## 5. Backend Patterns

### 5.1 Route File Pattern

Each API domain lives in its own file under `backend/app/routes/`. Every route file
exports a `router` variable:

```python
# backend/app/routes/analyze.py
from fastapi import APIRouter, Header, Depends
from typing import Optional

from app.dependencies import get_current_user
from app.models import AnalyzeRequest
from services.agent_controller import run_resume_pipeline
from services.db.lancedb_client import log_activity

router = APIRouter()


@router.post("/quality")
async def analyze_quality(
    request: AnalyzeRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    llm_config = {"api_key": x_openrouter_key, "model": x_llm_model} if x_openrouter_key else None
    output = run_resume_pipeline(task="score", resumes=[request.resume_text], llm_config=llm_config)
    return output
```

**Rules:**
- All routes are mounted with `/api/<domain>` prefix by the app factory.
- Route functions use `@router.post("/action")` (no `/api/` prefix in the route file).
- Use `async def` for all endpoints.
- Accept LLM config via `X-OpenRouter-Key` and `X-LLM-Model` headers.
- Use `Depends(get_current_user)` for authenticated endpoints.
- Return plain dicts (FastAPI auto-serializes to JSON).
- Use `print(f"DEBUG: ...")` for logging (not the `logging` module — that's a future migration).
- Import models from `app.models`, config from `app.config`, deps from `app.dependencies`.
- Import services with `from services.X import Y` (sys.path is set by the app factory).

### 5.2 Adding a New Route File

1. Create `backend/app/routes/<domain>.py` with a `router = APIRouter()`.
2. Register it in `backend/app/routes/__init__.py`.
3. Mount it in `backend/app/__init__.py` with `app.include_router(...)`.

### 5.3 Pydantic Request Models

Define in `backend/app/models.py`:

```python
class AnalyzeRequest(BaseModel):
    resume_text: str
    jd_text: Optional[str] = None
    threshold: Optional[int] = 75
```

**Rules:**
- Inherit from `BaseModel`.
- Use `Optional[T] = None` for optional fields.
- Use `Optional[T] = <default>` for fields with defaults.
- All models live in `backend/app/models.py`.

### 5.4 Import Order (Python)

```python
# 1. Standard library
import json
import os
from typing import List, Optional

# 2. Third-party
from fastapi import APIRouter, HTTPException, Header, Depends

# 3. App-level imports
from app.dependencies import get_current_user
from app.models import AnalyzeRequest
from app.config import UPLOAD_DIR

# 4. Service imports
from services.agent_controller import run_resume_pipeline
from services.db.lancedb_client import store_resume
```

### 5.5 Error Handling Pattern

```python
try:
    result = some_operation()
    return result
except Exception as e:
    print(f"DEBUG: Error in <context>: {e}")
    return {"error": f"<user-friendly message>: {str(e)}"}
```

**Rules:**
- Catch `Exception` broadly in endpoints; return error dicts, not 500s.
- Use `HTTPException` only for auth failures (401) and missing resources (404).
- Always include the error context in the print statement.
- Return a fallback dict structure matching the expected response shape.

---

## 6. AI / LangGraph Patterns

### 6.1 Graph File Template

Every new LangGraph workflow goes in `services/ai/` and follows this template:

```python
# services/ai/<feature>_graph.py
from typing import TypedDict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
import json
import os
from dotenv import load_dotenv
load_dotenv()


# ---------- State ----------
class FeatureState(TypedDict):
    input_field: str
    output_field: Optional[dict]
    config: Optional[dict]          # ALWAYS include config for dynamic LLM


# ---------- LLM Helper ----------
def get_llm(config: Optional[dict]):
    """Helper to initialize LLM from config or environment."""
    if config and config.get("api_key"):
        return ChatOpenAI(
            model=config.get("model", "gpt-4o-mini"),
            temperature=config.get("temperature", 0),
            api_key=config.get("api_key"),
            base_url=config.get("base_url", "https://openrouter.ai/api/v1")
        )
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPEN_ROUTER_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )


# ---------- Agents ----------
def feature_agent(state: FeatureState):
    llm = get_llm(state.get("config"))
    prompt = PromptTemplate(
        input_variables=["input"],
        template="""
You are an expert ...

Input:
{input}

TASK:
...

Return ONLY valid JSON:
{{
  "key": "value"
}}
"""
    )
    try:
        response = llm.invoke(prompt.format(input=state["input_field"]))
        from services.ai.skill_gap_graph import clean_json_output
        result = json.loads(clean_json_output(response.content))
        return {"output_field": result}
    except Exception as e:
        return {"output_field": {"error": str(e)}}


# ---------- Graph ----------
def build_feature_graph():
    graph = StateGraph(FeatureState)
    graph.add_node("process", feature_agent)
    graph.set_entry_point("process")
    graph.add_edge("process", END)
    return graph.compile()
```

### 6.2 Graph Registration

After creating a new graph, register it in `services/agent_controller.py`:

```python
from services.ai.feature_graph import build_feature_graph

_feature_graph = build_feature_graph()  # compile once at module load

def run_resume_pipeline(task: str, ...):
    if task == "feature":
        return _feature_graph.invoke({...})
    # ... existing tasks
```

**Rules:**
- Compile graphs at module load (top-level `_var = build_*_graph()`). Never compile per-request.
- Every state TypedDict MUST include `config: Optional[dict]`.
- Every agent function MUST use `get_llm(state.get("config"))`.
- Prompt templates MUST escape braces in JSON examples: `{{` and `}}`.
- Always use `clean_json_output()` from `services.ai.skill_gap_graph` before `json.loads()`.

### 6.3 Prompt Template Rules

```python
prompt = PromptTemplate(
    input_variables=["resume", "jd"],
    template="""
You are an expert <role>.

<Context Section>:
{resume}

TASK:
1. First step
2. Second step

Return ONLY valid JSON:
{{
  "field": "value"
}}
"""
)
```

**Rules:**
- Start with a role definition: `"You are an expert ..."`.
- Use labeled sections for context: `Resume:`, `Job Description:`, `Profile:`.
- Number the tasks.
- End with `"Return ONLY valid JSON:"` and the exact expected structure.
- Escape ALL braces in JSON examples: `{{` / `}}`.
- Use `PromptTemplate` from `langchain_core.prompts` (not f-strings).

---

## 7. Frontend Patterns

### 7.1 Component Template

```tsx
import React, { useState } from 'react';
import { IconName } from 'lucide-react';
import api from '../api';
import { useAuth } from '../context/AuthContext';

const FeaturePage = () => {
    const { persona, user } = useAuth();
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(false);

    const handleAction = async () => {
        setLoading(true);
        try {
            const response = await api.post('/endpoint', payload);
            setData(response.data);
        } catch (err: any) {
            console.error("Action failed:", err.response?.data || err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            <header>
                <h1 className="text-3xl font-bold mb-2 text-slate-900 tracking-tight">
                    Page Title
                </h1>
                <p className="text-slate-500 font-medium">Description.</p>
            </header>
            {/* content */}
        </div>
    );
};

export default FeaturePage;
```

### 7.2 API Calls

- **Use the `api` instance** from `frontend/src/api.ts` for all HTTP calls.
- The axios interceptor automatically attaches `Authorization`, `X-OpenRouter-Key`,
  `X-LLM-Model`, `X-LinkedIn-User`, and `X-LinkedIn-Pass` headers from `localStorage`.
- Do NOT use raw `fetch()` or create new axios instances.

```tsx
// CORRECT
import api from '../api';
const response = await api.post('/analyze/quality', { resume_text: text });

// WRONG — do not use fetch() directly
const response = await fetch('http://localhost:8000/api/analyze/quality', ...);
```

> **Note:** `Dashboard.tsx` currently uses raw `fetch()` — this is legacy and should not
> be replicated. All new code MUST use the `api` instance.

### 7.3 Routing

Routes are defined in `frontend/src/App.tsx`. To add a new page:

1. Create `frontend/src/pages/NewPage.tsx`.
2. Import and add a `<Route>` in `App.tsx`:

```tsx
import NewPage from './pages/NewPage';

<Route path="/new-page" element={
    <ProtectedRoute>
        <NewPage />
    </ProtectedRoute>
} />
```

3. Add the navigation link in `frontend/src/components/Sidebar.tsx`.

### 7.4 Styling Rules

- **Tailwind utility classes only.** No CSS files, no CSS modules, no inline `style={}`.
- Use the project's custom `primary` color scale defined in `tailwind.config.js`.
- Glass card pattern: `className="glass-card"` (defined in global CSS).
- Common patterns from existing code:

```
Cards:       "bg-white p-6 rounded-xl border border-slate-200 shadow-sm"
Headers:     "text-3xl font-bold mb-2 text-slate-900 tracking-tight"
Subtext:     "text-slate-500 font-medium"
Badges:      "text-[10px] font-black uppercase tracking-widest"
Buttons:     "bg-primary-600 hover:bg-primary-500 text-white px-6 py-3 rounded-lg font-bold"
```

### 7.5 State Management

- **Local state**: `useState` for component-scoped data.
- **Global state**: React Context (`AuthContext`). Do NOT add Redux, Zustand, or Jotai.
- **Persistent state**: `localStorage` for tokens and user settings.

```tsx
// Global state access
const { isAuthenticated, persona, user } = useAuth();

// Local state
const [results, setResults] = useState<any[]>([]);
```

### 7.6 TypeScript Rules

- Use `interface` for object shapes, `type` for unions and aliases.
- Use `<any>` sparingly; prefer typed interfaces. (Existing code uses `any` — do NOT
  make it worse, and prefer adding types when touching existing code.)
- Props typing inline for simple cases:

```tsx
const Layout = ({ children }: { children: React.ReactNode }) => { ... };
```

---

## 8. Database Patterns (LanceDB)

### 8.1 Schema

Two tables exist. Do NOT change the schema without updating all read/write code:

```python
# Resumes table — 1536-dim vectors (text-embedding-3-small)
resume_schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("user_id", pa.string()),
    pa.field("filename", pa.string()),
    pa.field("text", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 1536))
])

# Activity table — audit log
activity_schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("user_id", pa.string()),
    pa.field("type", pa.string()),
    pa.field("filename", pa.string()),
    pa.field("score", pa.int32()),
    pa.field("decision", pa.string()),
    pa.field("timestamp", pa.string())
])
```

### 8.2 Data Access Rules

- All DB operations go through `services/db/lancedb_client.py`.
- Use `get_or_create_table()` / `get_or_create_activity_table()` — never open tables directly.
- Use `user_id` filter on every query (multi-tenant isolation).
- UUIDs for `id` fields: `str(uuid4())`.
- Text chunking: 1000-char chunks with 200-char overlap (`chunk_text()`).

### 8.3 Embeddings

- Model: `text-embedding-3-small` via OpenRouter.
- Dimension: 1536.
- Cached in `_embeddings_cache` dict by `(api_key, model)` tuple.
- Always pass `api_key` from request headers when available.

---

## 9. Authentication Pattern

### Current Implementation (Mock)

- Frontend stores `token`, `persona`, and `user` in `localStorage`.
- Backend extracts user from `Authorization: Bearer <token>` header via `app/dependencies.py`.
- Mapping: `"recruiter"` or `"linkedin"` in token -> `user_recruiter_456`, else `user_alex_chen_123`.
- OAuth redirects go through `/api/auth/google` and `/api/auth/linkedin`.
- Callback redirects back to `http://localhost:5173/auth/callback?token=...`.

**Do NOT change the auth flow** without team discussion. Future migration to real JWT
is planned but not yet implemented.

---

## 10. Environment Variables

### Required Variables (in `backend/.env`)

See `.env.example` at project root for the template.

```
OPEN_ROUTER_KEY=<your-openrouter-api-key>
GOOGLE_CLIENT_ID=<google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<google-oauth-client-secret>
LINKEDIN_CLIENT_ID=<linkedin-oauth-client-id>
LINKEDIN_CLIENT_SECRET=<linkedin-oauth-client-secret>
LinkedinLogin=<linkedin-email-for-scraper>
LinkedinPassword=<linkedin-password-for-scraper>
```

**Rules:**
- All env vars are centralized in `backend/app/config.py`.
- Access via the config module: `from app.config import GOOGLE_CLIENT_ID`.
- For services that run outside the backend (tests, scripts), use `load_dotenv()` + `os.getenv()`.
- NEVER hardcode secrets. NEVER commit `.env` files.
- Frontend config (API keys, model names) is stored in `localStorage` and sent via headers.

---

## 11. Git & Collaboration Rules

### Branching

- `main` — stable, deployable code.
- `develop` — integration branch for features.
- Feature branches: `feature/<short-description>` (e.g., `feature/add-fraud-detection`).
- Bug fixes: `fix/<short-description>`.

### Commit Messages

```
<type>: <short description>

Types: feat, fix, refactor, docs, test, chore
```

Examples:
```
feat: add fraud detection graph
fix: handle empty resume text in quality scoring
refactor: extract LLM config helper to shared module
```

### What NOT to Commit

See `.gitignore` for the full list. Key items:
```
.env
backend/.env
data/raw_resumes/*
data/lancedb/*
node_modules/
__pycache__/
*.pyc
.DS_Store
dist/
.venv/
```

### Pull Request Checklist

Before merging, verify:
- [ ] Follows naming conventions from Section 3
- [ ] New endpoints in a route file under `backend/app/routes/`
- [ ] New route file registered in `routes/__init__.py` and `app/__init__.py`
- [ ] New graphs in `services/ai/` following the template in Section 6.1
- [ ] New graph registered in `services/agent_controller.py`
- [ ] New Pydantic models in `backend/app/models.py`
- [ ] New pages use `api` instance (not raw `fetch`)
- [ ] New routes added to `App.tsx` with `<ProtectedRoute>`
- [ ] No hardcoded secrets or localhost URLs in committed code
- [ ] No new dependencies added without approval
- [ ] Legacy code (`legacy/`) untouched

---

## 12. Common Utilities

### `clean_json_output()` — JSON Extraction

Located in `services/ai/skill_gap_graph.py`. Import and use whenever parsing LLM responses:

```python
from services.ai.skill_gap_graph import clean_json_output

raw = response.content           # might have ```json ... ```
clean = clean_json_output(raw)   # strips markdown fences
data = json.loads(clean)
```

### `get_llm()` — LLM Initialization

Duplicated in every graph file (by design — keeps graphs self-contained). Follow the
exact pattern: check `config` dict first, fall back to `.env`.

### `get_or_create_table()` — Table Access

Always use this. Never call `db.open_table()` or `db.create_table()` directly.

---

## 13. Development Workflow

### Starting the App

```bash
# Option 1: Automated (macOS/Linux)
./scripts/start_dev.sh

# Option 2: Automated (Windows)
start_app.bat

# Option 3: Manual
# Terminal 1 — Backend
cd backend && uvicorn main:app --reload

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Backend runs on `http://localhost:8000`, frontend on `http://localhost:5173`.

### Adding a New Feature (Checklist)

1. Define the LangGraph state TypedDict in `services/ai/<feature>_graph.py`.
2. Write agent functions with `get_llm()` pattern.
3. Build and compile the graph with `build_<feature>_graph()`.
4. Register in `services/agent_controller.py`.
5. Add Pydantic request model in `backend/app/models.py` (if needed).
6. Create route file in `backend/app/routes/<domain>.py` or add to existing one.
7. Register router in `backend/app/routes/__init__.py` and `backend/app/__init__.py`.
8. Create frontend page in `frontend/src/pages/<Feature>.tsx`.
9. Add route in `App.tsx` with `<ProtectedRoute>`.
10. Add nav link in `Sidebar.tsx`.

### Running Legacy Streamlit (if needed)

```bash
# From project root
PYTHONPATH=. streamlit run legacy/app.py
```

---

## 14. What Agents Must NEVER Do

1. **Never install new npm/pip packages** without explicit approval.
2. **Never modify** `services/db/lancedb_client.py` schema fields (adding fields is OK with approval).
3. **Never modify** legacy Streamlit files in `legacy/`.
4. **Never change** the auth flow or token mapping in `app/dependencies.py`.
5. **Never use** `logging` module — use `print(f"DEBUG: ...")` until logging migration is done.
6. **Never use** raw `fetch()` in frontend — use `api` instance from `api.ts`.
7. **Never create** CSS files — use Tailwind classes only.
8. **Never add** Redux, Zustand, MobX, or any state management library.
9. **Never change** CORS to production values without explicit deployment plan.
10. **Never commit** `.env`, `data/lancedb/`, or `data/raw_resumes/` contents.

---

## 15. Known Technical Debt

These are acknowledged issues. Do NOT fix them unless explicitly tasked:

| Issue | Location | Notes |
|---|---|---|
| `get_llm()` duplicated in every graph | `services/ai/*_graph.py` | Intentional — keeps graphs self-contained |
| `clean_json_output()` duplicated | `skill_gap_graph.py`, `linkedin_resume_graph.py` | Other files import from `skill_gap_graph` |
| `Dashboard.tsx` uses raw `fetch()` | `frontend/src/pages/Dashboard.tsx` | Should use `api` instance |
| Mock auth with hardcoded users | `backend/app/dependencies.py` | Real JWT planned |
| `print()` instead of structured logging | Everywhere | Migration to `loguru` planned |
| CORS set to `allow_origins=["*"]` | `backend/app/config.py` | Must restrict for production |
| No input sanitization on SQL-like where clauses | `services/db/lancedb_client.py` | `f"user_id = '{user_id}'"` — injection risk |
| No Docker / CI/CD | Project root | Planned as next infrastructure step |
| No API versioning | `backend/app/routes/` | All routes under `/api/` without version prefix |

---

*Last updated: 2026-02-21*
*Maintainer: Resume Intelligence Team*
