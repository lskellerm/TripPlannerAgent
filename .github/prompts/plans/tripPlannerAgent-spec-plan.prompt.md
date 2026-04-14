Airbnb Search & Analysis POC (v3)

## TL;DR

Build a Pydantic AI agent backed by `qwen3.5:35b-a3b` on Ollama (RTX 5080 FE) that autonomously searches Airbnb via Playwright MCP browser tools, extracts listing metadata, filters against user constraints, computes per-person cost breakdowns (multi-week, variable participant splits), and highlights "best" category listings. Backend: Python (FastAPI + Pydantic AI + Playwright MCP). Frontend: Nuxt 3 + PWA. Validated first with Pydantic AI’s built-in web UI.

> **Reference implementation**: Architecture, conventions, tooling, and Docker patterns mirror `lskellerm/JobApplicationAutomationTool`.

---

## Decided Constraints

- **GPU**: RTX 5080 FE (16GB GDDR7) — `qwen3.5:35b-a3b` is a MoE model (~3B active params) that fits entirely in VRAM. No CPU offloading needed.
- **Browser Automation**: Playwright MCP server (live scraping primary, cached HTML fallback)
- **Multi-week**: Supported from day one, with per-week participant lists and variable cost splits
- **Python**: >=3.13, managed by `uv` (matches JobAutoAgent convention)
- **Node**: pnpm package manager, Node 22 (matches JobAutoAgent frontend)
- **Formatting**: Ruff (tabs, double quotes, line-length 88) for Python; Prettier + ESLint for TypeScript
- **Observability**: Logfire instrumentation (FastAPI, httpx, asyncpg if applicable)

---

## Architecture

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

### Security & Authentication

The backend enforces layered authentication to ensure only authorized callers reach each route tier:

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
2. **Frontend → Backend** — All `/api/v1/agent/*` chat endpoints require a static API key sent via `X-API-Key` header. The key is generated at deploy time, stored in `settings.API_KEY` (env var `API_KEY`), and provided to the Nuxt frontend via `NUXT_PUBLIC_API_KEY` (or a server-side proxy that injects it). The backend validates with a lightweight `Depends(verify_api_key)` dependency.
3. **Agent-only (internal)** — If any internal routes exist that only the Pydantic AI agent should call (e.g., tool-execution endpoints, scraping triggers), they are guarded by a short-lived, self-issued JWT (`HS256`, `settings.AGENT_SECRET_KEY`). The agent receives a token at the start of each session via the `RunContext` dependency injection, and all internal `httpx` calls include it as `Authorization: Bearer <token>`. This prevents the frontend or any external caller from hitting agent-internal routes directly.

**Key rotation & secrets:**

- `API_KEY` — rotatable via env var, no restart required if using `pydantic-settings` with `env_file_encoding`
- `AGENT_SECRET_KEY` — `SecretStr`, used to sign/verify agent JWTs. Separate from `API_KEY` to isolate blast radius.
- Both secrets are in `.env` (gitignored) and `backend/.env.example` documents the required vars.

**CORS:**

- Strict `settings.CORS_ORIGINS` — defaults to `["http://localhost:3000"]` in dev, explicitly listed production origin(s). No wildcards.

**Rate limiting:**

- `slowapi` or custom middleware on `/api/v1/agent/chat` to prevent abuse (e.g., 10 req/min per IP in development, tunable via settings).

### Hybrid Tool Strategy

The agent gets TWO sets of tools:

1. **Playwright MCP toolset** — raw browser tools (navigate, click, type, snapshot, screenshot). The agent uses these to interact with Airbnb pages.
2. **Custom `@agent.tool` functions** — Airbnb-domain tools that handle URL construction, HTML parsing, filtering, cost math, and ranking. These encode the Airbnb-specific knowledge so the model doesn't need to reason about CSS selectors or DOM structure — it just calls `build_search_url(...)` then uses MCP to navigate, then calls `parse_search_results(html)` on the page content.

This hybrid approach lets `qwen3.5:35b-a3b` focus on high-level decision-making (what to search, how to filter) while the deterministic Python tools handle the fragile scraping logic.

---

## Steps

### Phase 1: Backend Core _(blocks all other phases)_

~~**Step 1. Project scaffolding & dependencies** _(mirrors JobAutoAgent conventions)_~~

- Initialize monorepo with `backend/` and `frontend/` top-level directories
- Root: `docker-compose.yml`, `.gitignore`, `.vscode/` (mcp.json, settings.json, extensions.json)
- **Backend** — `uv init` with `pyproject.toml` (Python >=3.13)
  - `.python-version` file: `3.13`
  - Dependencies:
    - `pydantic-ai[openai,mcp,web]` — agent framework + MCP client + built-in web UI
    - `fastapi>=0.115.0`, `uvicorn[standard]>=0.34.0` — API server
    - `pydantic[email]>=2.10.0`, `pydantic-settings>=2.7.0` — data models + env config
    - `beautifulsoup4`, `lxml` — HTML parsing in custom tools
    - `httpx>=0.28.0` — async HTTP client
    - `PyJWT>=2.9.0` — HS256 agent-scoped JWT issue/verify
    - `slowapi>=0.1.9` — rate limiting middleware
    - `logfire[fastapi,httpx]>=3.0.0` — observability
    - `playwright>=1.49.0` — browser automation (direct dependency for cached/fallback mode)
  - Dev dependencies: `ruff>=0.8.0`, `pytest>=8.3.0`, `pytest-asyncio>=0.25.0`
  - Ruff config: `target-version = "py313"`, `line-length = 88`, `indent-style = "tab"`, `quote-style = "double"`
  - `backend/.env.example` + `backend/.env` (gitignored)
  - Multi-stage `Dockerfile` (builder → development → production) using `uv` + Playwright browser install, Xvfb for headed anti-detection
- **Frontend** — `pnpm create nuxt` (Node 22, pnpm)
  - Nuxt 4 + `@pinia/nuxt`, `shadcn-nuxt`, `@tailwindcss/vite` (Tailwind v4)
  - `@hey-api/openapi-ts` for auto-generated type-safe API client from FastAPI OpenAPI schema
  - Prettier + ESLint config
  - Multi-stage `Dockerfile` (base → build → production using Nitro output)
  - `frontend/.env.example` with `NUXT_PUBLIC_API_BASE_URL`, `NUXT_PUBLIC_WS_BASE_URL`, `NUXT_API_KEY` (server-only, not public)
- Ensure `@playwright/mcp` npm package is available (installed globally or via `npx`)
- Directory structure:
  ```
  ├── docker-compose.yml
  ├── .vscode/
  │   ├── mcp.json
  │   ├── settings.json
  │   └── extensions.json
  ├── .github/
  │   ├── copilot-instructions.md
  │   └── prompts/
  ├── backend/
  │   ├── .python-version
  │   ├── .env.example
  │   ├── pyproject.toml
  │   ├── uv.lock
  │   ├── Dockerfile
  │   ├── .dockerignore
  │   └── src/
  │       ├── __init__.py
  │       ├── main.py              # FastAPI app factory + lifespan
  │       ├── database.py          # SQLite async engine (or future Postgres)
  │       ├── models.py            # SQLAlchemy Base
  │       ├── core/
  │       │   ├── __init__.py
  │       │   ├── config.py        # pydantic-settings Settings class
  │       │   ├── constants.py
  │       │   ├── dependencies.py  # FastAPI Depends
  │       │   ├── exceptions.py    # Custom exception classes
  │       │   ├── exception_handlers.py
  │       │   └── utils.py
  │       ├── auth/
  │       │   ├── __init__.py
  │       │   ├── api_key.py       # verify_api_key dependency
  │       │   ├── agent_jwt.py     # issue/verify agent-scoped JWTs
  │       │   └── dependencies.py  # require_api_key, require_agent_token
  │       ├── agent/
  │       │   ├── __init__.py
  │       │   ├── agent.py         # Pydantic AI agent + Playwright MCP config
  │       │   ├── schemas.py       # Pydantic schemas (TripWeek, AirbnbListing, etc.)
  │       │   └── router.py        # /api/v1/agent/* chat endpoints
  │       ├── airbnb/
  │       │   ├── __init__.py
  │       │   ├── tools/
  │       │   │   ├── __init__.py
  │       │   │   ├── urls.py      # build_search_url, build_listing_url
  │       │   │   ├── parsers.py   # parse_search_results, parse_listing_details
  │       │   │   └── analysis.py  # filter, cost breakdown, ranking
  │       │   └── schemas.py       # Airbnb-specific Pydantic models
  │       └── browser/
  │           ├── __init__.py
  │           └── handlers/        # Stealth/anti-detection if needed
  │
  └── frontend/
      ├── .env.example
      ├── Dockerfile
      ├── .dockerignore
      ├── package.json
      ├── pnpm-lock.yaml
      ├── nuxt.config.ts
      ├── openapi-ts.config.ts     # @hey-api codegen pointing at FastAPI
      ├── eslint.config.mjs
      ├── .prettierrc
      ├── components.json          # shadcn-vue config
      ├── api/                     # Auto-generated typed SDK
      │   ├── client.gen.ts
      │   ├── sdk.gen.ts
      │   ├── types.gen.ts
      │   └── index.ts
      ├── server/
      │   ├── api/
      │   │   └── agent/
      │   │       └── [...path].ts  # Proxy to FastAPI, injects X-API-Key server-side
      │   ├── routes/
      │   │   └── auth/             # (Phase 5) OAuth handler routes
      │   │       ├── google.get.ts
      │   │       ├── apple.get.ts
      │   │       └── github.get.ts
      │   └── middleware/
      │       └── auth.ts           # (Phase 5) requireUserSession gate
      └── app/
          ├── app.vue
          ├── assets/css/main.css
          ├── components/
          │   └── ui/              # shadcn-vue primitives
          ├── layouts/
          ├── pages/
          ├── plugins/
          ├── stores/              # Pinia stores
          └── lib/                 # Shared utilities
  ```

~~**Step 2. Core infrastructure** (`src/core/`, `src/main.py`, `src/database.py`)~~

- `src/core/config.py` — `Settings(BaseSettings)` with `pydantic-settings`, env file loading, typed fields:
  - `APP_NAME`, `ENVIRONMENT` (Literal["development", "production", "testing"]), `DEBUG`
  - `OLLAMA_BASE_URL`, `OLLAMA_MODEL_NAME`
  - `LOGFIRE_TOKEN` (SecretStr | None)
  - `CORS_ORIGINS` (list[str])
  - `API_V1_PREFIX` = "/api/v1"
  - `AIRBNB_SCRAPING_MODE` (Literal["live", "cached"])
  - `API_KEY` (SecretStr) — static key for frontend→backend authentication
  - `AGENT_SECRET_KEY` (SecretStr) — HS256 signing key for agent-scoped JWTs
  - `AGENT_TOKEN_EXPIRE_MINUTES` (int, default 30) — JWT TTL
  - `RATE_LIMIT_PER_MINUTE` (int, default 10) — chat endpoint rate limit
  - Computed `debug` property from `ENVIRONMENT`
- `FastAPIConfig(BaseSettings)` with `env_prefix="FASTAPI_"` — title, version, description, computed `openapi_url` (None in production)
- `src/main.py` — `create_app()` factory pattern (matches JobAutoAgent):
  - `lifespan()` async context manager for Logfire instrumentation + Playwright MCP lifecycle
  - CORS middleware from `settings.CORS_ORIGINS` (strict, no wildcards)
  - `generate_custom_unique_id` for OpenAPI operation IDs
  - Exception handlers via `register_exception_handlers()`
  - Router mounting: `app.include_router(agent_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(verify_api_key)])`
  - `/healthcheck` endpoint (public, no auth)
  - Security middleware ordering: CORS → rate limiting → auth dependencies per-router
- `src/database.py` — SQLite async engine (aiosqlite) for message history storage. Can upgrade to Postgres later if needed.
- `src/core/exceptions.py` + `src/core/exception_handlers.py` — structured error responses
- `src/core/dependencies.py` — FastAPI `Depends` for DB session, settings injection
- `src/auth/api_key.py` — `verify_api_key(x_api_key: str = Header(...))` dependency that compares against `settings.API_KEY` using constant-time `secrets.compare_digest()`. Returns `403` on mismatch.
- `src/auth/agent_jwt.py` — `issue_agent_token()` creates a short-lived HS256 JWT signed with `settings.AGENT_SECRET_KEY`, scoped to the current agent session. `verify_agent_token(authorization: str = Header(...))` decodes and validates. Used to gate agent-only internal endpoints.
- `src/auth/dependencies.py` — re-exports `require_api_key = Depends(verify_api_key)` and `require_agent_token = Depends(verify_agent_token)` for router-level injection

~~**Step 3. Pydantic data models** (`src/agent/schemas.py`, `src/airbnb/schemas.py`)~~

- `TripWeek` — week_label, check_in, check_out, location, neighborhood_constraints, participants (list[str]), num_people, min_bedrooms, min_bathrooms, min_rating, required_amenities, max_price_per_person
- `AirbnbListing` — url, title, total_cost, nightly_rate, num_beds, num_bedrooms, num_bathrooms, amenities (list[str]), neighborhood, rating, num_reviews, image_url (optional)
- `CostBreakdown` — total_cost, num_people, num_nights, cost_per_person, cost_per_night, cost_per_night_per_person, fees (dict: cleaning, service, etc.)
- `ListingWithCost` — listing (AirbnbListing) + cost_breakdown (CostBreakdown)
- `WeekAnalysis` — week (TripWeek), matched_listings (list[ListingWithCost]), best_price, best_value, best_amenities, best_location, best_reviews (each a ListingWithCost)
- `TripAnalysis` — weeks (list[WeekAnalysis]), per_person_totals (dict[str, float]), overall_summary (str)

~~**Step 4. Custom Airbnb-domain tools** (`src/airbnb/tools/`)~~

`urls.py`:

- `build_search_url(location, check_in, check_out, num_adults)` → returns Airbnb search URL string using the format from the cost doc. Generates random UUIDs for impression_id and federated_search_id.
- `build_listing_url(room_id, check_in, check_out, num_adults)` → returns individual listing URL

`parsers.py`:

- `parse_search_results(page_html: str)` → list of partial `AirbnbListing` objects (title, price preview, rating, URL, neighborhood) extracted with BeautifulSoup
- `parse_listing_details(page_html: str)` → enriched `AirbnbListing` (bedrooms, bathrooms, amenities, rating, reviews, full title)
- `parse_booking_price(page_html: str)` → `CostBreakdown` (total after fees, nightly rate, cleaning fee, service fee, etc.)

`analysis.py`:

- `filter_listings(listings, constraints: TripWeek)` → filtered list matching bedrooms, rating, amenities, neighborhood, price
- `calculate_cost_breakdown(total_cost, num_people, num_nights)` → `CostBreakdown`
- `calculate_trip_totals(week_analyses: list[WeekAnalysis], participant_names: list[str])` → per-person total across all weeks, accounting for which participants are present each week
- `rank_by_category(listings: list[ListingWithCost])` → dict of category → best listing pick

**Step 5. Configure agent with Playwright MCP** (`src/agent/agent.py`)
**current dev stage: (ongoing development)**

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

from src.core.config import settings

# Playwright MCP server as subprocess
playwright_server = MCPServerStdio(
    'npx', args=['@playwright/mcp@latest'],
    tool_prefix='browser'
)

# Ollama model — reads base URL from pydantic-settings
model = OpenAIChatModel(
    settings.OLLAMA_MODEL_NAME,
    provider=OllamaProvider(base_url=f"{settings.OLLAMA_BASE_URL}/v1")
)

agent = Agent(
    model,
    toolsets=[playwright_server],
    instructions="""You are an Airbnb search and trip cost analysis assistant.
    You help users find Airbnb listings for multi-week trips.

    Workflow:
    1. Use build_search_url() to construct Airbnb search URLs
    2. Use browser tools to navigate to the URL
    3. Get the page content and use parse_search_results() to extract listings
    4. For promising listings, navigate to each and use parse_listing_details()
    5. Navigate to booking page and use parse_booking_price() to get total cost
    6. Use filter_listings() to match user constraints
    7. Use calculate_cost_breakdown() for per-person costs
    8. Use rank_by_category() to highlight best picks
    9. Use calculate_trip_totals() for multi-week per-person summaries
    """,
    retries=2,
)

# Register custom tools via @agent.tool_plain decorators
```

**Step 6. Authentication module** (`src/auth/`)

- `src/auth/api_key.py`:

  ```python
  import secrets
  from fastapi import Header, HTTPException, status
  from src.core.config import settings

  async def verify_api_key(
      x_api_key: str = Header(..., alias="X-API-Key"),
  ) -> None:
      if not secrets.compare_digest(
          x_api_key.encode(), settings.API_KEY.get_secret_value().encode()
      ):
          raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
  ```

- `src/auth/agent_jwt.py`:

  ```python
  import jwt
  from datetime import datetime, timedelta, timezone
  from fastapi import Header, HTTPException, status
  from src.core.config import settings

  def issue_agent_token(session_id: str) -> str:
      payload = {
          "sub": "pydantic-ai-agent",
          "sid": session_id,
          "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.AGENT_TOKEN_EXPIRE_MINUTES),
          "iss": settings.APP_NAME,
      }
      return jwt.encode(payload, settings.AGENT_SECRET_KEY.get_secret_value(), algorithm="HS256")

  async def verify_agent_token(
      authorization: str = Header(...),
  ) -> dict:
      token = authorization.removeprefix("Bearer ").strip()
      try:
          return jwt.decode(
              token, settings.AGENT_SECRET_KEY.get_secret_value(),
              algorithms=["HS256"], issuer=settings.APP_NAME,
          )
      except jwt.InvalidTokenError as e:
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
  ```

- `src/auth/dependencies.py` — re-exports `require_api_key = Depends(verify_api_key)` and `require_agent_token = Depends(verify_agent_token)` for router-level use
- Agent receives its token via `RunContext.deps` at session start; all internal `httpx` calls include `Authorization: Bearer <token>`

**Step 7. Agent router & API integration** (`src/agent/router.py`) _(depends on Steps 5-6)_

- Mounted as `app.include_router(agent_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(verify_api_key)])` in `main.py`
- All agent chat endpoints require `X-API-Key` header (frontend sends it from `runtimeConfig`)
- `POST /api/v1/agent/chat` — user prompt → `agent.run_stream()` → newline-delimited JSON streaming response
- `GET /api/v1/agent/chat/history` — returns message history
- SQLite message storage (using Pydantic AI's `ModelMessagesTypeAdapter` for serialization)
- CORS middleware configured via `settings.CORS_ORIGINS` (defaults to `["http://localhost:3000"]`, no wildcards)
- Lifespan handler in `main.py` manages Playwright MCP server subprocess lifecycle (async with agent)
- OpenAPI schema auto-served at `/api/v1/openapi.json` (disabled in production via `FastAPIConfig`)
- Rate limiting on chat endpoint via `RATE_LIMIT_PER_MINUTE` setting

---

**Step 8. Docker Compose** _(parallel with Steps 2-7)_

- Profile-based `docker-compose.yml` mirroring JobAutoAgent pattern:
  - `infra` — just Ollama (GPU-accelerated)
  - `backend` — backend + Ollama (optional, `required: false`)
  - `frontend` — frontend + backend + Ollama
  - `full` — all services
- Services:
  - `ollama` — `ollama/ollama` image, GPU passthrough (`nvidia` driver), port 11434, volume `ollama_data`, healthcheck on `/v1/models`
  - `backend` — multi-stage Dockerfile (`uv` builder → production with Playwright + Xvfb), port 8000, env override for `OLLAMA_BASE_URL=http://ollama:11434`
  - `frontend` — pnpm + Nuxt 3 Dockerfile, port 3000, `NUXT_PUBLIC_API_BASE_URL=http://backend:8000`
- Networks: `backend-net`, `frontend-net`
- Volumes: `ollama_data`

---

### Phase 2: Validation _(parallel with Phase 3)_

**Step 9. Built-in Web UI validation**

- Use `agent.to_web()` to spin up Pydantic AI's built-in web chat UI
- Test prompts:
  - "Find 3-bedroom listings in Roma Norte, CDMX for May 2-9 for 4 adults"
  - "What's the per-person cost for Listing 1 if split between 4 people?"
  - Full multi-week: "Plan a 3-week trip to CDMX: Week 1 (Apr 24-May 2, 3 people, Roma Norte, 2BR), Week 2 (May 2-9, 4 people, 3BR), Week 3 (May 9-16, 3 people, 2-3BR)"
- Validate: Playwright MCP browser correctly loads Airbnb pages, parser tools extract accurate data, cost math matches expected values

**Step 10. Cached HTML fallback**

- If live scraping hits anti-bot blocks, implement fallback mode:
  - Load saved HTML from `discovery/` directory
  - `parse_search_results()` and `parse_listing_details()` work identically on cached HTML
  - Toggle via `settings.AIRBNB_SCRAPING_MODE` (env var: `AIRBNB_SCRAPING_MODE=live|cached`)

---

### Phase 3: Nuxt Frontend _(parallel with Phase 2)_

**Step 11. Nuxt 3 project setup** _(mirrors JobAutoAgent frontend)_

- `pnpm create nuxt frontend/` from monorepo root
- Install production deps: `@pinia/nuxt`, `shadcn-nuxt`, `@tailwindcss/vite` (Tailwind v4), `@tanstack/vue-query`, `@vueuse/core`, `vue-sonner`, `lucide-vue-next`, `reka-ui`, `class-variance-authority`, `clsx`, `tailwind-merge`, `nuxt-auth-utils` (Phase 5 — install early, enable later), `@vite-pwa/nuxt` (PWA support — configured in Step 11b)
- Install dev deps: `@hey-api/openapi-ts`, `eslint`, `eslint-config-prettier`, `eslint-plugin-prettier`, `prettier`, `tw-animate-css`, `vue-tsc`
- Configure `nuxt.config.ts`:
  - `modules: ['@nuxt/eslint', '@pinia/nuxt', 'shadcn-nuxt']`
  - `shadcn: { prefix: 'ui', componentDir: 'app/components/ui' }`
  - `runtimeConfig`: server-only `apiKey` (NUXT_API_KEY — never exposed to client)
  - `runtimeConfig.public`: `apiBaseUrl` (NUXT_PUBLIC_API_BASE_URL), `wsBaseUrl` (NUXT_PUBLIC_WS_BASE_URL)
  - `vite.plugins: [tailwindcss()]`
  - `typescript: { strict: true, typeCheck: true }`
  - `ssr: true`
- Configure `openapi-ts.config.ts` pointing at `http://localhost:8000/api/v1/openapi.json`
  - Plugins: `@hey-api/typescript`, `@hey-api/sdk`, `@hey-api/client-fetch`
  - Output to `api/` directory with Prettier post-processing
- `pnpm run api:generate` to create type-safe `api/client.gen.ts`, `api/sdk.gen.ts`, `api/types.gen.ts`

**Step 11b. PWA integration** _(depends on Step 11)_

- Add `'@vite-pwa/nuxt'` to the `modules` array in `nuxt.config.ts`
- Configure `pwa` options in `nuxt.config.ts`:
  - `registerType: 'autoUpdate'` — service worker auto-updates on new deployments
  - `manifest` — app name ("TripPlannerAgent"), short name, description, `display: 'standalone'`, `theme_color` matching the cyan/teal travel theme, icons (192×192 + 512×512 + maskable)
  - `workbox.navigateFallback: '/'` — offline shell falls back to cached chat page
  - `workbox.globPatterns` — cache HTML, CSS, JS, images, fonts
  - `workbox.runtimeCaching` — `CacheFirst` strategy for images (30-day expiration)
  - `devOptions: { enabled: true, type: 'module' }` — enable in dev for testing
- Create PWA icons in `public/icons/` (192×192, 512×512) + `favicon.ico`
- Ensure meta tags: `<meta name="theme-color">`, Apple touch icon, viewport
- Verify: Lighthouse PWA audit passes, app installs on mobile/desktop, service worker caches shell

**Step 12. Chat interface components**

- `app/pages/index.vue` — main chat layout
- `app/components/ChatMessage.vue` — renders user/agent messages, supports markdown
- `app/components/ChatInput.vue` — text input + send button
- `app/components/ListingCard.vue` — visual card for AirbnbListing (shows image, title, price, rating, amenities badges)
- `app/components/CostTable.vue` — tabular cost breakdown (per-person, per-night)
- `app/components/WeekSummary.vue` — week header with date range, participants, best picks
- `app/components/ui/` — shadcn-vue primitives (Button, Card, Input, etc.)
- `app/stores/chat.ts` — Pinia store for chat state management
- `app/plugins/api.ts` — initializes `@hey-api/client-fetch` with `runtimeConfig.public.apiBaseUrl`

**Step 13. Frontend-backend integration** _(depends on Steps 7 + 12)_

- Type-safe API calls via auto-generated `api/sdk.gen.ts` (no manual fetch boilerplate)
- **Server-side proxy** (preferred): `server/api/agent/[...path].ts` catches all `/api/agent/*` requests in Nitro, injects `X-API-Key` from private `runtimeConfig.apiKey` (env var `NUXT_API_KEY`), and forwards to FastAPI. The API key is **never exposed to the browser**.
  ```ts
  // frontend/server/api/agent/[...path].ts
  export default defineEventHandler(async (event) => {
    const config = useRuntimeConfig();
    const path = getRouterParam(event, "path") || "";
    const body = await readBody(event).catch(() => undefined);
    return $fetch(`/api/v1/agent/${path}`, {
      baseURL: config.public.apiBaseUrl,
      method: event.method,
      headers: { "X-API-Key": config.apiKey },
      body,
    });
  });
  ```
- Client-side components call `/api/agent/chat` (Nuxt route) — Nitro proxies to FastAPI with the key injected server-side
- Streaming `ReadableStream` to parse newline-delimited JSON from the proxied chat endpoint
- Detect structured data in agent responses and render appropriate components (ListingCard, CostTable)
- Display agent thinking/tool usage progress indicators
- Toast notifications via `vue-sonner`

---

### Phase 4: Integration & Polish

**Step 14. End-to-end testing** _(depends on Steps 9, 13)_

- Full multi-week flow test against known data from cost doc
- Verify per-person totals: Karina/Luis ~$1,150-$1,620, Mom ~$1,200-$1,650, Laura ~$400-$550
- Verify "Steps from Reforma" listing: 3BR/3BA, 4.91 stars, 126 reviews, $385.67/person

**Step 15. Error handling & resilience**

- Playwright MCP timeout → retry with backoff, inform user
- Airbnb anti-bot block → detect (CAPTCHA, empty results), switch to cached mode, notify user
- Ollama unavailable → graceful error with connection instructions
- Rate limiting: min 2s delay between Airbnb page loads

---

### Phase 5: OAuth Upgrade _(optional, zero backend changes)_

> **Prerequisite**: `nuxt-auth-utils` already installed in Step 11. This phase enables it.

**Step 16. Enable nuxt-auth-utils module & OAuth providers** _(depends on Step 13)_

All OAuth lives **entirely in the Nuxt server layer (Nitro)** — the FastAPI backend requires zero changes.

- Add `"nuxt-auth-utils"` to `modules` array in `nuxt.config.ts`
- Add env vars to `frontend/.env` (all auto-read by nuxt-auth-utils via `runtimeConfig`):
  - `NUXT_SESSION_PASSWORD` — ≥32 char random string for encrypted session cookies
  - `NUXT_OAUTH_GOOGLE_CLIENT_ID`, `NUXT_OAUTH_GOOGLE_CLIENT_SECRET`
  - `NUXT_OAUTH_APPLE_CLIENT_ID`, `NUXT_OAUTH_APPLE_CLIENT_SECRET`, `NUXT_OAUTH_APPLE_REDIRECT_URL`
  - `NUXT_OAUTH_GITHUB_CLIENT_ID`, `NUXT_OAUTH_GITHUB_CLIENT_SECRET`
- Create **OAuth handler routes** (one per provider):

  ```ts
  // frontend/server/routes/auth/google.get.ts
  export default defineOAuthGoogleEventHandler({
    async onSuccess(event, { user }) {
      await setUserSession(event, {
        user: {
          name: user.name,
          email: user.email,
          avatar: user.picture,
          provider: "google",
        },
      });
      return sendRedirect(event, "/");
    },
  });
  ```

  ```ts
  // frontend/server/routes/auth/apple.get.ts
  export default defineOAuthAppleEventHandler({
    async onSuccess(event, { user }) {
      await setUserSession(event, {
        user: { name: user.name, email: user.email, provider: "apple" },
      });
      return sendRedirect(event, "/");
    },
  });
  ```

  ```ts
  // frontend/server/routes/auth/github.get.ts
  export default defineOAuthGitHubEventHandler({
    async onSuccess(event, { user }) {
      await setUserSession(event, {
        user: {
          name: user.name || user.login,
          email: user.email,
          avatar: user.avatar_url,
          provider: "github",
        },
      });
      return sendRedirect(event, "/");
    },
  });
  ```

- Create **auth middleware** to gate all pages behind login:

  ```ts
  // frontend/server/middleware/auth.ts
  export default defineEventHandler(async (event) => {
    // Skip auth routes and public assets
    const path = getRequestURL(event).pathname;
    if (path.startsWith("/auth/") || path.startsWith("/_nuxt/")) return;

    // Gate API proxy routes — only authenticated users can reach the backend
    if (path.startsWith("/api/agent/")) {
      const session = await requireUserSession(event);
      // session.user is available for audit logging if needed
    }
  });
  ```

- Create **login page** (`app/pages/login.vue`):
  - Three OAuth buttons: "Sign in with Google", "Sign in with Apple", "Sign in with GitHub"
  - Each links to `/auth/google`, `/auth/apple`, `/auth/github` respectively
  - Use `useUserSession()` composable to check auth state and redirect if already logged in

- Update **app layout** to show user avatar/name + logout button:
  - `useUserSession()` composable provides `loggedIn`, `user`, `clear()` (logout)
  - Logout calls `clear()` which invalidates the encrypted session cookie

- **Auth flow summary**:

  ```
  Browser → /auth/google → Google consent → callback → setUserSession()
         → encrypted h3 cookie set → redirect to /
         → /api/agent/chat → server middleware validates session
                            → Nitro proxy injects X-API-Key → FastAPI
  ```

- **No backend changes needed**: OAuth sessions live in Nitro's encrypted cookies (h3). The server-side proxy (Step 13) already injects `X-API-Key` privately. The middleware just adds a session gate before the proxy.

---

## Relevant Files

- `CDMX_trip_airbnb_cost.md` — listing metadata schema, search URL format, cost breakdown reference, multi-week trip structure
- `discovery/AirBnB_example_search_page.html` — saved search results page (parser test fixture)
- `discovery/Steps from Reforma...html` — saved listing detail page (parser test fixture, ground truth: 3BR/3BA, 4.91★, 126 reviews)

## Verification

1. Parse saved HTML in `discovery/` → assert "Steps from Reforma" extracts to 3BR/3BA, 4.91 stars, 126 reviews
2. Agent tool-calling: use `TestModel` to verify correct tool sequence (build_url → browser_navigate → parse → filter → rank)
3. Cost math: $1542.66 / 4 people / 7 nights = $385.67/person, $55.09/person/night
4. Multi-week totals: sum per-person costs across weeks accounting for variable participants
5. Streaming: verify FastAPI endpoint sends incremental JSON chunks
6. PWA: verify Nuxt app installs on mobile, service worker caches shell
7. Auth: verify requests without `X-API-Key` return 403; verify expired/invalid agent JWTs return 401; verify rate limiting rejects excess requests
8. OAuth (Phase 5): verify unauthenticated requests to `/api/agent/*` are redirected to login; verify session cookie is set after OAuth callback; verify logout clears session

## Conventions (from JobAutoAgent)

| Concern                  | Convention                                                                                                            |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Python version           | >=3.13, `.python-version` file                                                                                        |
| Package manager (Python) | `uv` (lockfile: `uv.lock`)                                                                                            |
| Package manager (Node)   | `pnpm` (lockfile: `pnpm-lock.yaml`)                                                                                   |
| Python formatting        | Ruff — tabs, double quotes, line-length 88                                                                            |
| TypeScript formatting    | Prettier + ESLint                                                                                                     |
| Backend structure        | `src/` package, domain modules (`agent/`, `airbnb/`, `browser/`, `core/`)                                             |
| Config                   | `pydantic-settings` with `.env` files, `Settings` singleton                                                           |
| FastAPI                  | App factory (`create_app()`), lifespan context manager, custom exception handlers, `/healthcheck`                     |
| OpenAPI operation IDs    | `generate_custom_unique_id()` for clean client codegen                                                                |
| API versioning           | `/api/v1` prefix                                                                                                      |
| Frontend API client      | `@hey-api/openapi-ts` auto-generated SDK from FastAPI OpenAPI schema                                                  |
| Frontend state           | Pinia stores                                                                                                          |
| Frontend UI              | shadcn-vue (prefix `ui`), Tailwind v4, lucide-vue-next icons                                                          |
| Frontend PWA             | `@vite-pwa/nuxt` — service worker, web manifest, installable app shell                                                |
| Observability            | Logfire (FastAPI, httpx, asyncpg instruments)                                                                         |
| Docker                   | Multi-stage builds, profile-based compose, non-root users, healthchecks                                               |
| Anti-detection           | Xvfb headed mode, Playwright browser install in Docker                                                                |
| Auth (frontend→backend)  | Static API key via `X-API-Key` header, injected server-side by Nitro proxy, validated with `secrets.compare_digest()` |
| Auth (frontend OAuth)    | `nuxt-auth-utils` — Google, Apple, GitHub providers; encrypted session cookies; zero backend changes                  |
| Auth (agent-internal)    | Self-issued HS256 JWT scoped per session, injected via `RunContext.deps`                                              |
| Secrets                  | `SecretStr` fields in `Settings`, `.env` gitignored, `.env.example` documents required vars                           |
| Rate limiting            | Per-endpoint, configurable via `RATE_LIMIT_PER_MINUTE` setting                                                        |
| CORS                     | Strict origin list, no wildcards                                                                                      |

## Decisions

1. **Hybrid tools (Playwright MCP + custom parsers)**: Playwright MCP provides browser control, custom `@agent.tool` functions handle Airbnb-specific URL building, HTML parsing, cost math, and ranking. This split keeps fragile scraping logic deterministic while letting the model orchestrate the workflow.
2. **`qwen3.5:35b-a3b` on RTX 5080 FE**: MoE architecture with ~3B active parameters fits entirely in 16GB VRAM. Fast inference without CPU offloading.
3. **Live scraping first**: Playwright MCP for real-time Airbnb interaction. Cached HTML fallback toggleable via env var.
4. **Multi-week from start**: Data models and cost calculation support variable participants per week, per-person trip totals across weeks.
5. **POC validation via `agent.to_web()`** before investing in Nuxt frontend.
6. **Mirror JobAutoAgent stack**: Same tooling (`uv`, `pnpm`, Ruff, Prettier), same FastAPI patterns (app factory, pydantic-settings, Logfire, exception handlers), same Nuxt patterns (shadcn-vue, Pinia, `@hey-api/openapi-ts`), same Docker patterns (multi-stage, profiles, GPU passthrough).
7. **`@hey-api/openapi-ts` for frontend-backend contract**: Auto-generate typed SDK from FastAPI's OpenAPI schema — eliminates manual type duplication and ensures frontend stays in sync with backend endpoints.
8. **Layered authentication**: Three tiers (public / API-key-gated / agent-JWT-gated) to enforce that only the Nuxt frontend can reach chat endpoints and only the Pydantic AI agent can call internal tool/scraping routes. API key for simplicity (no user accounts needed for a POC), agent JWTs for internal route isolation.
9. **No user auth for initial POC**: The API key gates the frontend→backend boundary; the agent JWT gates agent-internal routes. Phase 5 adds OAuth (Google, Apple, GitHub) via `nuxt-auth-utils` when ready — entirely in the Nuxt server layer with zero backend changes.
10. **OAuth via nuxt-auth-utils (Phase 5)**: Google, Apple, and GitHub providers. All auth logic lives in Nitro server routes and middleware. Sessions stored in encrypted h3 cookies. The server-side proxy pattern (Step 13) means the API key is never exposed to the browser — the middleware simply adds a session gate before the existing proxy. No `fastapi-users` or backend auth changes needed.
11. **Server-side API key injection**: The Nuxt server proxy (`server/api/agent/[...path].ts`) injects `X-API-Key` from private `runtimeConfig.apiKey` (env var `NUXT_API_KEY`). The key is never in `runtimeConfig.public` and never reaches the browser.
