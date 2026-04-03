# TripPlannerAgent — AI Agent Guide

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
  - [Hybrid Tool Strategy](#hybrid-tool-strategy)
  - [Observability](#observability)
- [Scraping & Anti-Detection](#scraping--anti-detection)
- [Frontend Patterns](#frontend-patterns)
- [Common Tasks](#common-tasks)
- [Important Constraints](#important-constraints)
- [Coding Style Guidelines](#coding-style-guidelines)
- [Frontend Coding Style Guidelines](#frontend-coding-style-guidelines)

## Project Overview

This is an AI-powered Airbnb search and trip cost analysis platform with a FastAPI backend and Nuxt 3 + PWA frontend. A Pydantic AI agent backed by `qwen3.5:35b-a3b` on Ollama (local LLM, RTX 5080 FE GPU) autonomously searches Airbnb via Playwright MCP browser tools, extracts listing metadata, filters against user constraints, computes per-person cost breakdowns (multi-week, variable participant splits), and highlights "best" category listings — all through a conversational chat interface.

**Core features:**

- Conversational chat interface for natural-language Airbnb trip planning
- Autonomous Airbnb search and listing analysis via Playwright MCP browser automation
- Hybrid tool strategy: Playwright MCP (raw browser) + custom `@agent.tool` functions (Airbnb-domain logic)
- Multi-week trip support with per-week participant lists and variable cost splits
- Per-person cost breakdowns with fee decomposition (cleaning, service, etc.)
- Categorical ranking of listings (best price, best value, best amenities, best location, best reviews)
- Dual scraping modes: live browser (primary) + cached HTML fallback (anti-bot resilience)
- Server-side API key proxy — secrets never exposed to the browser
- Self-hosted via Docker Compose with local LLM (Ollama GPU-accelerated)

## Architecture

### System Flow

```
┌──────────────────────┐        ┌─────────────────────────────────────────┐
│  Nuxt 3 + PWA        │◄──────►│  FastAPI Backend (uv + Python 3.13)     │
│  (pnpm, shadcn-vue,  │  API   │                                         │
│   @hey-api/openapi-ts│        │  ┌───────────────────────────────────┐  │
│   Pinia, Tailwind v4)│        │  │  Pydantic AI Agent                 │  │
└──────────────────────┘        │  │  (OllamaProvider: qwen3.5:35b-a3b)    │  │
                                │  │                                    │  │
         docker-compose         │  │  Toolsets:                         │  │
         ┌──────────┐           │  │  ├─ Playwright MCP (browser)       │  │
         │  Ollama   │           │  │  │  navigate, click, snapshot      │  │
         │  (GPU)    │           │  │  │                                 │  │
         └──────────┘           │  │  ├─ @agent.tool (custom):          │  │
                                │  │  │  build_search_url               │  │
                                │  │  │  parse_search_results           │  │
                                │  │  │  parse_listing_details          │  │
                                │  │  │  parse_booking_price            │  │
                                │  │  │  filter_listings                │  │
                                │  │  │  calculate_cost_breakdown       │  │
                                │  │  │  rank_by_category               │  │
                                │  │  └─────────────────────────────────│  │
                                │  └───────────────────────────────────┘  │
                                │                                         │
                                │  Playwright MCP Server (subprocess)     │
                                │  (@playwright/mcp via npx)              │
                                │                                         │
                                │  Logfire (observability)                │
                                └─────────────────────────────────────────┘
```

- **`backend/src/core/`**: Cross-cutting concerns — global config (`Settings`, `FastAPIConfig`), base exceptions, shared dependencies, constants (enums)
- **`backend/src/auth/`**: Layered authentication — static API key (`X-API-Key` header) for frontend→backend, agent-scoped HS256 JWT for internal agent-only routes
- **`backend/src/agent/`**: Pydantic AI agent definition (`agent.py`), chat router (`router.py`), data schemas (`schemas.py`)
- **`backend/src/airbnb/`**: Airbnb-domain logic — URL builders, HTML parsers (BeautifulSoup), filtering, cost breakdown math, categorical ranking
- **`backend/src/browser/`**: Browser automation handlers and stealth/anti-detection if needed
- **`backend/src/models.py`** / **`backend/src/database.py`**: SQLAlchemy Base + async SQLite engine for message history persistence
- **`frontend/`**: Nuxt 3 (Vue 3) + PWA with shadcn-vue components, TanStack Query for server state, Pinia for UI-only client state, Nitro server-side proxy for API key injection

### Security & Authentication

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Route Tiers & Auth                            │
├───────────────────────┬──────────────────────┬────────────────────────┤
│  Public               │  Frontend → Backend  │  Agent-only (internal) │
│  /healthcheck         │  /api/v1/agent/chat   │  /api/v1/internal/*    │
│  (no auth)            │  (API key via header) │  (agent-scoped JWT)    │
└───────────────────────┴──────────────────────┴────────────────────────┘
```

**Three tiers:**

1. **Public** — `/healthcheck` only, no authentication.
2. **Frontend → Backend** — All `/api/v1/agent/*` chat endpoints require a static API key sent via `X-API-Key` header. The Nuxt Nitro server proxy (`server/api/agent/[...path].ts`) injects the key server-side from `runtimeConfig.apiKey` — **never exposed to the browser**.
3. **Agent-only (internal)** — Internal routes guarded by a short-lived, self-issued HS256 JWT (`settings.AGENT_SECRET_KEY`). The agent receives a token via `RunContext.deps` at session start.

**Key rotation & secrets:**

- `API_KEY` — rotatable via env var, constant-time comparison via `secrets.compare_digest()`
- `AGENT_SECRET_KEY` — `SecretStr`, used to sign/verify agent JWTs. Separate from `API_KEY` to isolate blast radius.
- Both secrets are in `.env` (gitignored) and `backend/.env.example` documents the required vars.

**CORS:** Strict `settings.CORS_ORIGINS` — defaults to `["http://localhost:3000"]` in dev. No wildcards.

**Rate limiting:** `slowapi` on `/api/v1/agent/chat` — configurable via `RATE_LIMIT_PER_MINUTE` setting (default: 10).

### Codebase Structure

```
TripPlannerAgent/
├── .github/
│   ├── copilot-instructions.md          # This file — AI agent onboarding guide
│   ├── agents/                          # AI agent definitions (Excalidraw diagramming, etc.)
│   └── prompts/
│       └── plans/
│           └── tripPlannerAgent-spec-plan.prompt.md  # Full implementation plan
├── backend/
│   ├── pyproject.toml                   # Dependencies (uv managed)
│   ├── .python-version                  # 3.13
│   ├── Dockerfile                       # Multi-stage (builder → dev → prod)
│   └── src/
│       ├── __init__.py                  # Eager model imports
│       ├── main.py                      # FastAPI app factory + lifespan (Logfire + MCP lifecycle)
│       ├── database.py                  # SQLite async engine (aiosqlite) for message history
│       ├── models.py                    # SQLAlchemy Base model
│       ├── core/
│       │   ├── config.py               # Settings(BaseSettings) + FastAPIConfig(BaseSettings)
│       │   ├── constants.py            # Environment, ScrapingMode enums + HTTP status aliases
│       │   ├── exceptions.py           # AppException base + domain-specific hierarchy
│       │   ├── exception_handlers.py   # FastAPI exception handler registration
│       │   ├── dependencies.py         # FastAPI Depends (DB session, settings)
│       │   └── utils.py
│       ├── auth/
│       │   ├── api_key.py              # verify_api_key — constant-time X-API-Key comparison
│       │   ├── agent_jwt.py            # issue_agent_token / verify_agent_token (HS256 JWT)
│       │   └── dependencies.py         # require_api_key, require_agent_token re-exports
│       ├── agent/
│       │   ├── agent.py                # Pydantic AI agent + Playwright MCP + custom tools
│       │   ├── schemas.py              # TripWeek, AirbnbListing, CostBreakdown, etc.
│       │   └── router.py              # POST /agent/chat (streaming) + GET /agent/chat/history
│       ├── airbnb/
│       │   ├── schemas.py              # Airbnb-specific Pydantic models
│       │   └── tools/
│       │       ├── urls.py             # build_search_url, build_listing_url
│       │       ├── parsers.py          # parse_search_results, parse_listing_details, parse_booking_price
│       │       └── analysis.py         # filter_listings, calculate_cost_breakdown, rank_by_category
│       └── browser/
│           └── handlers/               # Stealth/anti-detection handlers
├── discovery/
│   └── html/                            # Cached Airbnb HTML pages for fallback scraping mode
├── frontend/
│   ├── nuxt.config.ts                   # Modules, runtimeConfig, Tailwind v4, Pinia, shadcn
│   ├── package.json                     # pnpm managed
│   ├── openapi-ts.config.ts             # @hey-api codegen → api/ directory
│   ├── eslint.config.mjs
│   ├── components.json                  # shadcn-vue config
│   ├── server/
│   │   └── api/agent/[...path].ts       # Nitro proxy — injects X-API-Key server-side
│   └── app/
│       ├── app.vue
│       ├── assets/css/main.css          # Tailwind v4 CSS
│       ├── components/ui/               # shadcn-vue primitives (Badge, Button, Card, Input, Sonner)
│       ├── composables/                 # TanStack Query wrappers (useChat, etc.)
│       ├── layouts/default.vue
│       ├── lib/utils.ts                 # tailwind-merge + clsx utilities
│       ├── pages/index.vue              # Main chat interface
│       ├── plugins/vue-query.ts         # TanStack Query plugin registration
│       └── stores/
│           ├── chat.ts                  # Chat streaming state (UI-only)
│           └── ui.ts                    # General UI state
└── docker-compose.yml                   # ollama (GPU), backend, frontend — profile-based
```

### Module Conventions

Every backend module under `src/` follows this internal structure pattern:

- **`__init__.py`**: Explicit re-exports with typed `__all__: list[str]` + eager model imports
- **`schemas.py`**: Pydantic request/response schemas
- **`router.py`**: FastAPI `APIRouter` with endpoints
- **`config.py`**: Module-specific `BaseSettings` singleton with `SettingsConfigDict(env_prefix="MODULE_")`
- **`constants.py`**: Enums and magic values
- **`dependencies.py`**: FastAPI `Depends()` callables
- **`exceptions.py`**: Module-specific exception hierarchy inheriting from `core.exceptions`
- **`utils.py`**: Helper functions

## Key Development Patterns

### Environment & Dependencies

- **Python 3.13+** (per `.python-version`)
- Use `uv` for dependency management (`uv sync` to install from `uv.lock`)
- **Backend runtime**: `fastapi`, `uvicorn[standard]`, `pydantic[email]`, `pydantic-settings`, `pydantic-ai`, `sqlalchemy`, `aiosqlite`, `beautifulsoup4`, `lxml`, `httpx`, `PyJWT`, `slowapi`, `logfire[fastapi,httpx]`, `playwright`
- **Backend dev**: `ruff`, `pytest`, `pytest-asyncio`, `ty`
- **Ruff config**: `target-version = "py313"`, `line-length = 88`, `indent-style = "tab"`, `quote-style = "double"`
- **Frontend**: Nuxt 3, `shadcn-vue`, `reka-ui`, `tailwindcss` (v4 via `@tailwindcss/vite`), `pinia`, `@tanstack/vue-query`, `@vueuse/core`, `lucide-vue-next`, `vue-sonner`
- **Frontend dev**: `@nuxt/eslint` (Nuxt ESLint module), `eslint`, `prettier`, `eslint-config-prettier`, `eslint-plugin-prettier`, `typescript`, `vue-tsc`
- **Frontend package manager**: `pnpm` — used exclusively for all frontend dependency management. Never use `npm` or `yarn`.
- **API Client Generation**: `@hey-api/openapi-ts` — auto-generates typed TS client from FastAPI OpenAPI spec into `frontend/api/`

### Async-First

All I/O operations must use async libraries — this is a hard architectural requirement:

- Database: `aiosqlite` + `sqlalchemy` async engine (never synchronous SQLite)
- HTTP: `httpx.AsyncClient` (never `requests`)
- Browser: `playwright.async_api` (never sync API)

### Code Quality

- **Backend**: Use **Ruff** for linting and formatting (`ruff check .`, `ruff format .`) and **ty** for type checking (`uv run ty .`).
- **Frontend**: Use **ESLint** via `@nuxt/eslint` module (flat config) for linting + **Prettier** for formatting (`pnpm run lint`, `pnpm run format`). ESLint config is auto-generated in `.nuxt/eslint.config.mjs` and extended via the root `eslint.config.mjs`. Use `eslint-config-prettier` to disable ESLint rules that conflict with Prettier.
- Pydantic models for all data validation and typed structures
- Google-style docstrings for all modules, classes, and functions in python and Jsdoc for TypeScript, with `Args:`, `Returns:`, `Raises:` sections
- Type hints on all function signatures

### General Notes

- Reference [tripPlannerAgent-spec-plan.prompt.md](../.github/prompts/plans/tripPlannerAgent-spec-plan.prompt.md) for the full implementation plan with phased steps and detailed architecture
- All documentation lives in markdown files with a Table of Contents section, located in their stack-specific directories (`backend/docs/`, `frontend/docs/`), `.github/` for cross-cutting topics like AI agent design and prompt engineering, root-level for stack wide guidelines (`backend/README.md`, `frontend/README.md`).
- After an implementation effort, update the relevant documentation files with new patterns, architectural decisions, and code examples to keep the knowledge base current for future contributors.

## Backend Patterns

### FastAPI best practices:

Follow ALL of the best practices mentioned in the [FastAPI documentation](https://fastapi.tiangolo.com) and best practices from the [FastAPI Best Practices Public repo](https://github.com/zhanymkanov/fastapi-best-practices)

### Pydantic Models

Follow the frozen model pattern for read/response schemas:

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Union

class CostBreakdownRead(BaseModel):
	"""Read schema for a cost breakdown result."""
	model_config = ConfigDict(frozen=True)

	total_cost: float = Field(description="Total cost of the listing stay.")
	cost_per_person: float = Field(description="Cost per person for the stay.")
	cost_per_night: float = Field(description="Cost per night for the listing.")
	fees: Union[dict[str, float], None] = Field(
		default=None, description="Fee breakdown (cleaning, service, etc.)."
	)
```

### Configuration

One `BaseSettings` per module, loaded from `.env`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=".env", env_file_encoding="utf-8",
		case_sensitive=False, extra="ignore",
	)
	OLLAMA_BASE_URL: str = "http://localhost:11434"
	OLLAMA_MODEL_NAME: str = "qwen3.5:35b-a3b"
	API_KEY: SecretStr
	AGENT_SECRET_KEY: SecretStr
```

### Exception Hierarchies

Each module has its own exception hierarchy inheriting from a base:

```python
# core/exceptions.py
class AppException(Exception):
	"""Base exception for all application errors."""
	pass

class NotFoundException(AppException): ...
class ForbiddenException(AppException): ...

# airbnb/exceptions.py (future)
class ScrapingError(AppException): ...
class AntiBotDetectedError(ScrapingError): ...
class RateLimitExceededError(ScrapingError): ...
```

### Auth Module

The auth module uses a layered approach — **not** `fastapi-users`:

- `api_key.py`: `verify_api_key()` — constant-time `secrets.compare_digest()` comparison of `X-API-Key` header against `settings.API_KEY`
- `agent_jwt.py`: `issue_agent_token(session_id)` creates short-lived HS256 JWT signed with `settings.AGENT_SECRET_KEY`; `verify_agent_token()` decodes and validates
- `dependencies.py`: Re-exports `require_api_key = Depends(verify_api_key)` and `require_agent_token = Depends(verify_agent_token)` for router-level injection

## AI Agent Architecture

### Hybrid Tool Strategy

The agent gets **two sets of tools**:

1. **Playwright MCP toolset** — raw browser tools (`navigate`, `click`, `type`, `snapshot`, `screenshot`). The agent uses these to interact with Airbnb pages directly.
2. **Custom `@agent.tool` functions** — Airbnb-domain tools that handle URL construction, HTML parsing, filtering, cost math, and ranking. These encode the Airbnb-specific knowledge so the model doesn't need to reason about CSS selectors or DOM structure.

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

# Playwright MCP server as subprocess
playwright_server = MCPServerStdio(
	'npx', args=['@playwright/mcp@latest'],
	tool_prefix='browser'
)

# Ollama model via OpenAI-compatible endpoint
model = OpenAIChatModel(
	settings.OLLAMA_MODEL_NAME,
	provider=OllamaProvider(base_url=f"{settings.OLLAMA_BASE_URL}/v1")
)

agent = Agent(
	model,
	toolsets=[playwright_server],
	instructions="...",
	retries=2,
)

# Custom tools registered via @agent.tool_plain decorators
```

**Agent workflow:**

1. `build_search_url()` → construct Airbnb search URL
2. Playwright MCP `navigate` → load page
3. `parse_search_results(html)` → extract listing previews
4. For promising listings: navigate + `parse_listing_details(html)` → full metadata
5. `parse_booking_price(html)` → cost with fees
6. `filter_listings()` → match user constraints
7. `calculate_cost_breakdown()` → per-person costs
8. `rank_by_category()` → best picks per category
9. `calculate_trip_totals()` → multi-week per-person summaries

### Observability

Logfire auto-instruments the full stack — no manual logging calls needed:

```python
import logfire
logfire.configure()
logfire.instrument_fastapi(app)
logfire.instrument_httpx()
# Pydantic AI auto-instruments when logfire is installed
```

## Scraping & Anti-Detection

| Layer                | Implementation                                                                   |
| -------------------- | -------------------------------------------------------------------------------- |
| **Scraping mode**    | `AIRBNB_SCRAPING_MODE` setting: `live` (Playwright MCP) or `cached` (saved HTML) |
| **Cached fallback**  | `discovery/html/` directory with saved Airbnb search/listing pages               |
| **Rate limiting**    | Minimum 2s delay between Airbnb page loads                                       |
| **Anti-bot detect**  | CAPTCHA / empty results detection → switch to cached mode + notify user          |
| **Circuit breaker**  | 3 consecutive failures → pause session + inform user                             |
| **Browser handlers** | `browser/handlers/` for any stealth/anti-detection extensions                    |

## Frontend Patterns

- **API Client**: Auto-generated via `@hey-api/openapi-ts` from FastAPI's `/api/v1/openapi.json`. Run `cd frontend && pnpm run api:generate` after any backend endpoint or schema change. Generated output lives in `frontend/api/`. Composables import from `~/api/` — never hand-write `$fetch` calls for backend endpoints that have generated clients.
- **Server-side Proxy**: `server/api/agent/[...path].ts` catches all `/api/agent/*` requests in Nitro, injects `X-API-Key` from private `runtimeConfig.apiKey`, and forwards to FastAPI. The API key is **never exposed to the browser**.
- **Server State**: TanStack Query (`@tanstack/vue-query`) handles all server data — fetching, caching, background refresh, and mutation. Composables use `useQuery` / `useMutation` with generated API service functions as `queryFn`.
- **Client State**: Pinia stores hold **UI-only state** — streaming state, filters, modal open/closed. Never duplicate server data in Pinia; let TanStack Query own it.
- **Components**: shadcn-vue (copy-paste, owned in `components/ui/`) built on Reka UI + Tailwind CSS v4
- **Composables**: Reusable logic in `composables/` (useChat, etc.). Each composable wraps `useQuery`/`useMutation` calls with appropriate query keys and invalidation logic.
- **Routing**: File-based via Nuxt pages (`pages/index.vue` — main chat interface)
- **Streaming**: Agent responses stream via newline-delimited JSON; `ReadableStream` parsing on the client
- **Package Manager**: `pnpm` is the exclusive package manager for the frontend. All commands use `pnpm` (e.g., `pnpm install`, `pnpm run dev`, `pnpm add <pkg>`). The `pnpm-lock.yaml` lockfile is committed to version control. Never use `npm` or `yarn`.
- **Linting**: `@nuxt/eslint` Nuxt module generates a project-aware ESLint flat config. Extend it in `eslint.config.mjs` at the frontend root. Append `eslint-config-prettier` last to disable style rules that conflict with Prettier.
- **Formatting**: Prettier handles all code formatting. Configure via `.prettierrc` at the frontend root. Prettier and ESLint do not overlap — ESLint covers correctness rules only.

## Common Tasks

**Install backend dependencies:** `cd backend && uv sync`

**Run backend:** `cd backend && uv run uvicorn src.main:app --reload`

**Run agent web UI (validation):** `cd backend && uv run python -c "from src.agent.agent import agent; agent.to_web()"`

**Check code (backend):** `cd backend && uv run ruff check . && uv run ruff format .`

**Type check (backend):** `cd backend && uv run ty .`

**Run tests:** `cd backend && uv run pytest`

**Install frontend dependencies:** `cd frontend && pnpm install`

**Run frontend:** `cd frontend && pnpm run dev`

**Lint frontend:** `cd frontend && pnpm run lint` (fix: `pnpm run lint:fix`)

**Format frontend:** `cd frontend && pnpm run format`

**Type check frontend:** `cd frontend && pnpm run typecheck`

**Generate API client:** `cd frontend && pnpm run api:generate`

**Docker Compose (backend + Ollama):** `docker compose --profile backend up --build`

**Docker Compose (full stack):** `docker compose --profile full up --build`

## Important Constraints

- Always create github issues (and any relevant sub-issues) for a new feature, bug, or architectural change before implementing. Link the issue in the commit message (e.g., `git commit -m "Add Airbnb search URL builder tool (#12)"`).
- All backend I/O must be async — synchronous calls will block the event loop and break Playwright automation
- Ollama is accessed only through Pydantic AI's `OpenAIChatModel` + `OllamaProvider` — never use the raw `ollama` Python library directly
- Playwright MCP server lifecycle is managed by the FastAPI lifespan handler in `main.py`
- The `auth/` module uses static API key + agent-scoped JWT — **not** `fastapi-users`
- `CORS_ORIGINS` must be explicit — no wildcards. Defaults to `["http://localhost:3000"]`
- The Nuxt Nitro proxy (`server/api/agent/[...path].ts`) must inject the API key server-side — never expose `API_KEY` to the browser
- Scraping mode is toggled via `AIRBNB_SCRAPING_MODE` env var (`live` or `cached`)
- `discovery/html/` contains cached Airbnb pages for fallback/testing — parsers must work identically on cached and live HTML
- Rate limit Airbnb page loads: minimum 2s delay between requests

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
- Use tabs for indentation, double quotes for strings (Ruff enforced)

## Frontend Coding Style Guidelines

- Use `pnpm` for all frontend package management commands
- API client functions are auto-generated in `frontend/api/` — import and use these in composables instead of writing raw `$fetch` calls
- Use TanStack Query (`useQuery`, `useMutation`) for all server state management in composables
- Pinia stores are for UI state only — never duplicate server data here
- Use shadcn-vue components for all UI elements, customizing via Tailwind CSS as needed
- ESLint handles code correctness rules, Prettier handles all formatting — do not overlap configurations
- Write JSDoc comments for all components, composables, and stores with `@param`, `@returns`, and `@throws` annotations
- Always run `pnpm run lint`, `pnpm run format`, and `pnpm run typecheck` before committing code to ensure quality and consistency
