# Job Application Automation Tool — AI Agent Guide

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
  - [System Flow](#system-flow)
  - [Codebase Structure](#codebase-structure)
  - [Module Conventions](#module-conventions)
- [Key Development Patterns](#key-development-patterns)
  - [Environment & Dependencies](#environment--dependencies)
  - [Async-First](#async-first)
  - [Code Quality](#code-quality)
  - [General Notes](#general-notes)
- [Backend Patterns](#backend-patterns)
  - [Pydantic Models](#pydantic-models)
  - [Configuration](#configuration)
  - [Exception Hierarchies](#exception-hierarchies)
  - [Auth Module](#auth-module)
- [AI Agent Architecture](#ai-agent-architecture)
  - [Pydantic AI Agents](#pydantic-ai-agents)
  - [Dual-Mode Browser Automation](#dual-mode-browser-automation)
  - [Observability](#observability)
- [Anti-Detection](#anti-detection)
- [Frontend Patterns](#frontend-patterns)
- [Common Tasks](#common-tasks)
- [Important Constraints](#important-constraints)
- [Coding Style Guidelines](#coding-style-guidelines)

## Project Overview

This is an AI-powered autonomous job application platform with a FastAPI backend and Nuxt 3 frontend. It uses applicant context (resume, LinkedIn, GitHub) to auto-apply to jobs via browser automation, with a dashboard for tracking application status and real-time agent monitoring.

**Core features:**

- Autonomous job application workflows via Playwright browser automation
- AI-powered job matching and content tailoring via Pydantic AI + Ollama (local LLM)
- Dual-mode browser interaction: deterministic handlers for known sites (LinkedIn, Indeed) + MCP-driven adaptive agent for unknown sites
- Real-time WebSocket monitoring of agent activity
- Anti-detection: stealth browsers, fingerprint rotation, behavioral humanization, proxy management
- Human-in-the-loop for CAPTCHAs, ambiguous fields, and approval gates
- Self-hosted via Docker Compose with local LLM (Ollama)

## Architecture

### System Flow

- **`backend/src/auth/`**: User authentication via `fastapi-users` (JWT + Google OAuth + email verification) — mirrors `FinanceAutomaterPlatform-Backend`
- **`backend/src/profiles/`**: Applicant profile management — resume upload/parsing, LinkedIn/GitHub links, structured context storage
- **`backend/src/jobs/`**: Job sourcing from APIs (Adzuna, JSearch) + AI matching via `matching_agent`
- **`backend/src/agent/`**: Pydantic AI agent layer — `application_agent`, `matching_agent`, `tailoring_agent` + `pydantic_graph` workflow state machine
- **`backend/src/ai/`**: LLM provider abstraction — `OllamaModel` factory, system prompt templates
- **`backend/src/browser/`**: Playwright automation with stealth subsystem + per-site handlers
- **`backend/src/applications/`**: Application tracking — status transitions, event logging, audit trail
- **`backend/src/notifications/`**: In-app + email notifications via WebSocket (Redis pub/sub)
- **`backend/src/workers/`**: TaskIQ async task queue — background job processing
- **`backend/src/core/`**: Cross-cutting concerns — global config, base exceptions, shared dependencies
- **`frontend/`**: Nuxt 3 (Vue 3) SPA with shadcn-vue components, TanStack Query for server state, Pinia for client state, WebSocket composables

### Codebase Structure

```
JobApplicationAutomationTool/
├── .github/
│   ├── copilot-instructions.md
│   ├── agents/                          # AI agent definitions (Excalidraw diagramming, etc.)
│   └── prompts/
│       └── plan-jobApplicationAutomationTool.prompt.md  # Full implementation plan
├── backend/
│   ├── pyproject.toml                   # Dependencies (uv managed)
│   ├── .python-version                  # 3.13
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                       # Async migration support
│   │   └── versions/
│   └── src/
│       ├── __init__.py                  # Eager model imports for Alembic discovery
│       ├── main.py                      # FastAPI app factory + Logfire init + lifespan
│       ├── database.py                  # create_async_engine, async_sessionmaker, Base
│       ├── core/
│       │   ├── config.py                # Settings(BaseSettings) — DATABASE_URL, REDIS_URL, etc.
│       │   ├── constants.py
│       │   ├── exceptions.py            # AppException base + NotFoundException, ForbiddenException
│       │   ├── dependencies.py          # get_async_session, get_current_user
│       │   └── utils.py
│       ├── auth/                        # fastapi-users (mirrors FinanceAutomater)
│       │   ├── config.py               # AuthSettings — JWT secret, Google OAuth, SMTP
│       │   ├── models.py               # User(SQLAlchemyBaseUserTableUUID, Base)
│       │   ├── schemas.py              # UserRead, UserCreate, UserUpdate
│       │   ├── router.py               # fastapi_users.get_*_router() inclusion
│       │   ├── services.py             # UserManager(UUIDIDMixin, BaseUserManager)
│       │   ├── transport.py            # BearerTransport + JWTStrategy + AuthenticationBackend
│       │   ├── utils.py                # get_user_db, get_user_manager generators
│       │   └── dependencies.py         # current_active_user, current_superuser
│       ├── profiles/                    # Applicant profile + resume management
│       ├── jobs/                        # Job sourcing + AI matching
│       ├── applications/                # Application tracking + events
│       ├── ai/
│       │   ├── config.py               # AIConfig — ollama_base_url, model_name
│       │   ├── provider.py             # get_ollama_model() → OllamaModel factory
│       │   └── prompts.py              # System prompt templates
│       ├── agent/
│       │   ├── agents.py               # application_agent, matching_agent, tailoring_agent
│       │   ├── tools.py                # @agent.tool decorated functions
│       │   ├── graph.py                # pydantic_graph ApplicationState workflow
│       │   ├── mcp.py                  # MCPServerStdio wrapper for @playwright/mcp
│       │   ├── models.py               # AgentSession DB model
│       │   └── router.py               # /agent/sessions endpoints + WebSocket
│       ├── browser/
│       │   ├── context.py              # Async context manager for browser lifecycle
│       │   ├── stealth/
│       │   │   ├── profiles.py         # BrowserProfile dataclass + profiles_db.json
│       │   │   ├── fingerprint.py      # Fingerprint randomization
│       │   │   ├── behavior.py         # HumanizedInteractor (Bézier mouse, Gaussian typing)
│       │   │   ├── proxy.py            # ProxyManager (rotation, sticky sessions)
│       │   │   └── captcha.py          # CapSolver/2Captcha + user fallback
│       │   └── handlers/
│       │       ├── base.py             # BaseJobSiteHandler ABC
│       │       ├── linkedin.py         # LinkedIn Easy Apply handler
│       │       └── indeed.py           # Indeed Apply handler
│       ├── notifications/               # In-app + email via WebSocket
│       └── workers/
│           ├── broker.py               # RedisBroker setup
│           └── tasks.py                # TaskIQ task definitions
├── frontend/                            # Nuxt 3 (Vue 3) + shadcn-vue + TanStack Query + Pinia
│   ├── nuxt.config.ts
│   ├── api/                             # auto-generated API client (@hey-api/openapi-ts)
│   ├── components/ui/                   # shadcn-vue components (owned in source)
│   ├── composables/                     # useAuth, useJobs, useAgent, useWebSocket (TanStack Query wrappers)
│   ├── stores/                          # Pinia stores (UI-only: auth token, filters, modals, WS buffer)
│   ├── pages/                           # index, login, profile, jobs/, applications/, agent/
│   └── middleware/auth.global.ts
└── docker-compose.yml                   # db, redis, ollama, backend, worker, frontend
```

### Module Conventions

Every backend module under `src/` follows this internal structure pattern (from `FinanceAutomaterPlatform-Backend` and `hol_automations`):

- **`__init__.py`**: Explicit re-exports with typed `__all__: list[str]` + eager model imports
- **`models.py`**: SQLAlchemy ORM models (async-compatible)
- **`schemas.py`**: Pydantic request/response schemas
- **`router.py`**: FastAPI `APIRouter` with endpoints
- **`services.py`**: Business logic (all async)
- **`config.py`**: Module-specific `BaseSettings` singleton with `SettingsConfigDict(env_prefix="MODULE_")`
- **`constants.py`**: Enums and magic values
- **`dependencies.py`**: FastAPI `Depends()` callables
- **`exceptions.py`**: Module-specific exception hierarchy inheriting from `core.exceptions`
- **`utils.py`**: Helper functions

## Key Development Patterns

### Environment & Dependencies

- **Python 3.13+** (per `.python-version`)
- Use `uv` for dependency management (`uv sync` to install from `uv.lock`)
- **Backend runtime**: `fastapi`, `pydantic[email]`, `pydantic-settings`, `pydantic-ai[ollama,logfire]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `fastapi-users[sqlalchemy]`, `taskiq`, `taskiq-redis`, `taskiq-fastapi`, `playwright`, `camoufox`, `httpx`, `redis`, `logfire[fastapi,sqlalchemy,httpx,asyncpg]`
- **Backend dev**: `ruff`, `pytest`, `pytest-asyncio`
- **Frontend**: Nuxt 3, `shadcn-vue`, `reka-ui`, `tailwindcss` (v4 via `@tailwindcss/vite`), `pinia`, `@tanstack/vue-query`, `@vueuse/core`, `lucide-vue-next`
- **Frontend dev**: `@nuxt/eslint` (Nuxt ESLint module), `eslint`, `prettier`, `eslint-config-prettier`, `eslint-plugin-prettier`, `typescript`
- **Frontend package manager**: `pnpm` — used exclusively for all frontend dependency management. Never use `npm` or `yarn`.
- **API Client Generation**: `@hey-api/openapi-ts` + `@hey-api/client-fetch` — auto-generates typed TS client from FastAPI OpenAPI spec

### Async-First

All I/O operations must use async libraries — this is a hard architectural requirement:

- Database: `async_sessionmaker` + `asyncpg` (never synchronous `psycopg2`)
- HTTP: `httpx.AsyncClient` (never `requests`)
- Browser: `playwright.async_api` (never sync API)
- Task queue: `TaskIQ` (not Celery — chosen specifically for async compatibility with Playwright)
- Redis: `redis.asyncio`

### Code Quality

- **Backend**: Use **Ruff** for linting and formatting (`ruff check .`, `ruff format .`)
- **Frontend**: Use **ESLint** via `@nuxt/eslint` module (flat config) for linting + **Prettier** for formatting (`pnpm run lint`, `pnpm run format`). ESLint config is auto-generated in `.nuxt/eslint.config.mjs` and extended via the root `eslint.config.mjs`. Use `eslint-config-prettier` to disable ESLint rules that conflict with Prettier.
- Pydantic models for all data validation and typed structures
- Google-style docstrings for all modules, classes, and functions in python and Jsdoc for TypeScript, with `Args:`, `Returns:`, `Raises:` sections
- Type hints on all function signatures

### General Notes

- Reference [plan-jobApplicationAutomationTool.prompt.md](../.github/prompts/plan-jobApplicationAutomationTool.prompt.md) for the full implementation plan with database schema, phased steps, and detailed architecture
- The `auth/` module must mirror the `fastapi-users` setup from `FinanceAutomaterPlatform-Backend` exactly (JWT + Google OAuth + email verification)
- All documentation lives in markdown files with a Table of Contents section, located in their stack-specific directories (`backend/docs/`, `frontend/docs/`), `.github/` for cross-cutting topics like AI agent design and prompt engineering, root-level for stack wide guidelines (`backend/README.md`, `frontend/README.md`).
- After an implementation effort, update the relevant documentation files with new patterns, architectural decisions, and code examples to keep the knowledge base current for future contributors.

## Backend Patterns

### FastAPI best practices:

Follow FastAPI conventions for routers, dependencies, and settings similar to the `FinanceAutomaterPlatform-Backend`:

Follow ALL of the best practices mentioned in the [FastAPI documentation](https://fastapi.tiangolo.com) and best practices from the [FastAPI Best Practices Public repo](https://github.com/zhanymkanov/fastapi-best-practices)

### Pydantic Models

Follow the frozen model pattern from `agora_log_viewer_tui` when applicable:

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Union

class JobMatchRead(BaseModel):
    """Read schema for a job match result."""
    model_config = ConfigDict(frozen=True)

    job_title: str = Field(description="Title of the matched job listing.")
    match_score: float = Field(description="AI-computed match score (0.0–1.0).")
    reasoning: Union[str, None] = Field(
        default=None, description="LLM explanation of the match."
    )
```

### Configuration

One `BaseSettings` per module, loaded from `.env`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class AIConfig(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL_NAME: str = "llama3.1"

ai_config: AIConfig = AIConfig()
```

### Exception Hierarchies

Each module has its own exception hierarchy inheriting from a base (from `agora_log_viewer_tui` pattern):

```python
# core/exceptions.py
class AppException(Exception):
    """Base exception for all application errors."""
    pass

class NotFoundException(AppException): ...
class ForbiddenException(AppException): ...

# browser/exceptions.py
class BrowserError(AppException): ...
class CaptchaDetectedError(BrowserError): ...
class RateLimitExceededError(BrowserError): ...
```

### Auth Module

The auth module mirrors `FinanceAutomaterPlatform-Backend` using `fastapi-users`:

- `models.py`: `User(SQLAlchemyBaseUserTableUUID, Base)` with `oauth_accounts` relationship
- `transport.py`: `BearerTransport` + `JWTStrategy` + `AuthenticationBackend`
- `services.py`: `UserManager(UUIDIDMixin, BaseUserManager)` with lifecycle hooks
- `router.py`: Include `fastapi_users.get_auth_router()`, `get_register_router()`, `get_verify_router()`, `get_oauth_router()`

## AI Agent Architecture

### Pydantic AI Agents

Three specialized agents defined in `agent/agents.py`:

- **`application_agent`**: Orchestrates a single job application (form filling, submission)
- **`matching_agent`**: Scores job listings against user profile, returns `MatchResult`
- **`tailoring_agent`**: Generates cover letters and tailored resume content

Each agent uses `@agent.tool` decorated functions from `agent/tools.py` and receives dependencies via `RunContext[Deps]`.

### Dual-Mode Browser Automation

- **Known sites** (LinkedIn, Indeed): Deterministic Playwright handlers in `browser/handlers/` with CSS/XPath selectors. Fast and reliable.
- **Unknown sites**: `application_agent` uses `MCPServerStdio("npx", ["@playwright/mcp@latest", "--headless"])` to reason about page structure via accessibility tree snapshots and act via `browser_click`/`browser_type`.

Both modes use `HumanizedInteractor` from `browser/stealth/behavior.py` for anti-detection.

### Observability

Logfire auto-instruments the full stack — no manual logging calls needed:

```python
import logfire
logfire.configure()
logfire.instrument_fastapi(app)
logfire.instrument_sqlalchemy(engine)
logfire.instrument_httpx()
logfire.instrument_asyncpg()
# Pydantic AI auto-instruments when logfire is installed
```

## Anti-Detection

| Layer               | Implementation                                                                                                       |
| ------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Browser**         | camoufox (Firefox-based) or rebrowser-playwright (Chromium CDP patches)                                              |
| **Fingerprint**     | Random UA, viewport, WebGL, canvas noise, timezone per session (`browser/stealth/profiles.py`)                       |
| **Behavior**        | Bézier mouse curves, Gaussian typing (μ=80ms, σ=20ms), natural scrolls, think pauses (`browser/stealth/behavior.py`) |
| **Network**         | Residential proxies with sticky sessions per application flow (`browser/stealth/proxy.py`)                           |
| **Rate limits**     | LinkedIn: 5 apps/hr, Indeed: 10 apps/hr (configurable in `browser/config.py`)                                        |
| **CAPTCHA**         | CapSolver/2Captcha API primary + user WebSocket fallback (`browser/stealth/captcha.py`)                              |
| **Circuit breaker** | 3 consecutive failures → pause session + notify user                                                                 |

## Frontend Patterns

- **API Client**: Auto-generated via `@hey-api/openapi-ts` from FastAPI's `/openapi.json`. Run `cd frontend && pnpm run api:generate` after any backend endpoint or schema change. Generated output lives in `frontend/api/` (typed service functions + request/response types). Composables import from `~/api/` — never hand-write `$fetch` calls for backend endpoints that have generated clients.
- **Server State**: TanStack Query (`@tanstack/vue-query`) handles all server data — fetching, caching, background refresh, and mutation. Composables use `useQuery` / `useMutation` with generated API service functions as `queryFn`. WebSocket events trigger `queryClient.invalidateQueries()` to keep cached data fresh.
- **Client State**: Pinia stores hold **UI-only state** — selected filters, modal open/closed, sidebar collapsed, live WS event buffer. Never duplicate server data in Pinia; let TanStack Query own it.
- **Components**: shadcn-vue (copy-paste, owned in `components/ui/`) built on Radix Vue + Tailwind CSS
- **Composables**: Reusable logic in `composables/` (useAuth, useJobs, useAgent, etc.). Each composable wraps `useQuery`/`useMutation` calls with appropriate query keys and invalidation logic.
- **Routing**: File-based via Nuxt 3 pages (`pages/jobs/[id].vue`, `pages/applications/index.vue`)
- **Auth middleware**: `middleware/auth.global.ts` redirects unauthenticated users
- **Package Manager**: `pnpm` is the exclusive package manager for the frontend. All commands use `pnpm` (e.g., `pnpm install`, `pnpm run dev`, `pnpm add <pkg>`). The `pnpm-lock.yaml` lockfile is committed to version control. Never use `npm` or `yarn`.
- **Linting**: `@nuxt/eslint` Nuxt module generates a project-aware ESLint flat config. Extend it in `eslint.config.mjs` at the frontend root. Append `eslint-config-prettier` last to disable style rules that conflict with Prettier.
- **Formatting**: Prettier handles all code formatting. Configure via `.prettierrc` at the frontend root. Prettier and ESLint do not overlap — ESLint covers correctness rules only.

## Common Tasks

**Install backend dependencies:** `cd backend && uv sync`

**Run backend:** `cd backend && uv run uvicorn src.main:app --reload`

**Run TaskIQ worker:** `cd backend && uv run taskiq worker src.workers.broker:broker`

**Run migrations:** `cd backend && uv run alembic upgrade head`

**Create migration:** `cd backend && uv run alembic revision --autogenerate -m "description"`

**Check code (backend):** `cd backend && uv run ruff check . && uv run ruff format .`

**Install frontend dependencies:** `cd frontend && pnpm install`

**Lint frontend:** `cd frontend && pnpm run lint` (fix: `pnpm run lint:fix`)

**Format frontend:** `cd frontend && pnpm run format`

**Run tests:** `cd backend && uv run pytest`

**Run frontend:** `cd frontend && pnpm run dev`

**Generate API client:** `cd frontend && pnpm run api:generate`

**Docker Compose (full stack):** `docker compose up --build`

## Important Constraints

- Always create github issues (and any relevant sub-issues) for a new feature, bug, or architectural change before implementing. Link the issue in the commit message (e.g., `git commit -m "Add new API endpoint for job matching (#123)"`).
- All backend I/O must be async — synchronous calls will block the event loop and break Playwright automation
- TaskIQ was chosen over Celery specifically because Celery cannot run async Playwright tasks
- The `auth/` module must use `fastapi-users` exactly as `FinanceAutomaterPlatform-Backend` does — do not roll custom JWT logic
- Browser automation runs in headed mode via Xvfb in Docker (not headless) for anti-detection
- `src/__init__.py` must eagerly import all SQLAlchemy models so Alembic can discover them for autogeneration
- Ollama is accessed only through Pydantic AI's `OllamaModel` — never use the raw `ollama` Python library directly
- Rate limits are per-site, per-user — LinkedIn 5 apps/hr, Indeed 10 apps/hr

## Coding Style Guidelines

- Use `Union[X, None]` for optional types (not `X | None` or `Optional[X]`)
- Use `model_config = ConfigDict(frozen=True)` for read/response Pydantic schemas
- Use `Field(description="...")` on all Pydantic model attributes
- Write Google-style docstrings with `Args:`, `Returns:`, `Raises:` sections
- Every `__init__.py` must have explicit re-exports with typed `__all__: list[str]`
- One `BaseSettings` singleton per module with `SettingsConfigDict(env_prefix="...")`
- Exception classes inherit from module-specific base → `core.exceptions.AppException`
- Constants live in `constants.py` (never inline magic values)
- Prefer strong typing: determine actual types where possible, minimizing use of `Any`
- Always include a Table of Contents section at the top of markdown files

## Frontend Coding Style Guidelines

- Use `pnpm` for all frontend package management commands
- API client functions are auto-generated in `frontend/api/` — import and use these in composables instead of writing raw `$fetch` calls
- Use TanStack Query (`useQuery`, `useMutation`) for all server state management in composables
- Pinia stores are for UI state only — never duplicate server data here
- Use shadcn-vue components for all UI elements, customizing via Tailwind CSS as needed
- ESLint handles code correctness rules, Prettier handles all formatting — do not overlap configurations
- Write JSDoc comments for all components, composables, and stores with `@param`, `@returns`, and `@throws` annotations
- Always run `pnpm run lint`, `pnpm run format`, and `pnpm run typecheck` before committing code to ensure quality and consistency
