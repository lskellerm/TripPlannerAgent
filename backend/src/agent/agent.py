"""Pydantic AI agent instance with Playwright MCP and custom Airbnb search tools.

Configures the central Pydantic AI agent (``agent harness``) that orchestrates Airbnb searches using a hybrid tool strategy:

1. **Playwright MCP toolset** — raw browser tools (navigate, click, snapshot)
   for interacting with Airbnb pages via a subprocess MCP server.
2. **Custom Airbnb toolset** — domain-specific ``FunctionToolset`` with URL
   builders, HTML parsers, cost computation, filtering, and ranking.

The agent uses ``qwen3.5:35b-a3b`` hosted on Ollama, accessed through Pydantic AI's
``OllamaProvider``.  Playwright MCP runs as a stdio subprocess managed by the
FastAPI lifespan (see ``src.main``).

Context Window Configuration
----------------------------
Ollama's OpenAI-compatible ``/v1/chat/completions`` endpoint does **not**
support the ``options.num_ctx`` parameter — it silently ignores it.  To
set the context window size, a **derived model** with ``num_ctx`` baked
in is created at startup via Ollama's native ``/api/create`` endpoint.
Call :func:`configure_agent_model` during application startup (FastAPI
lifespan) to ensure the derived model exists and update the agent.
"""

from pathlib import Path
from typing import Union

from httpx import AsyncClient, Client, Limits, Response, Timeout
from logfire import (
	configure,
	info,
	instrument_httpx,
	instrument_pydantic_ai,
	instrument_starlette,
	warning,
)
from pydantic_ai import Agent, ModelSettings, SetMetadataToolset, Tool
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai_harness import CodeMode
from starlette.applications import Starlette

from src.airbnb.tools import (
	build_listing_url,
	build_search_url,
	calculate_trip_totals,
	explore_listings,
	filter_search_results,
	parse_booking_price,
	parse_listing_details,
	parse_listing_page,
	parse_search_results,
	rank_by_category,
	verify_constraints,
)
from src.core.config import settings
from src.core.utils import configure_logfire

# ── Logfire Instrumentation and Configuration (module-level) ──
configure_logfire(
	settings=settings,
	engine=None,  # Replace
	fastapi_app=None,  # Replace with your FastAPI app instance if needed
	disble_scrubbing=False
	if not settings.DEBUG
	else True,  # Disable scrubbing in dev mode for full log visibilityy
	web_chat_enabled=False
	if not settings.DEBUG
	else True,  # Enable web chat in dev mode
)

logfire_token: Union[str, None] = (
	settings.LOGFIRE_TOKEN.get_secret_value() if settings.LOGFIRE_TOKEN else None
)

configure(
	token=logfire_token,
	environment=settings.ENVIRONMENT,
	service_name="TripPlannerAgent-Dev",
)
instrument_pydantic_ai()
instrument_httpx()

# ── System Instructions ──

# ── System Instructions ──

# TODO: Replace inline progress reporting with `pydantic-ai-todo`
# TodoCapability for structured real-time progress streaming to the
# frontend.  See: https://github.com/vstorm-co/pydantic-ai-todo


AGENT_INSTRUCTIONS: str = """\
You are an expert Trip planner agent and Airbnb search specialist. Your task is to search Airbnb,
analyse listings, compute cost breakdowns, and recommend the best options
to the user.

## Workflow

Follow these steps when the user asks you to plan a trip or find Airbnb listings:

1. **Build Search URL** — Call `build_search_url(location, check_in, check_out,
   number_of_adults)` to construct a properly formatted Airbnb search URL.
   **Pass pre-filter parameters** to narrow results at the source:
   - `min_bedrooms`, `min_bathrooms`, `min_beds` — room requirements
   - `required_amenities` — list of amenity short-names (e.g.
     `["wifi", "ac", "kitchen", "washer"]`)
   - `room_type` — one of `"entire_home"`, `"private_room"`, `"shared_room"`
   - `price_min`, `price_max` — nightly price range in USD
   This dramatically reduces irrelevant results.

2. **Navigate to Search Page** — Use `browser_navigate(url)` to load the URL.

3. **Wait for Page to Load** — Use `browser_wait_for(text="for <N> nights")`
   where `<N>` is the number of nights.  Fallback indicators: "beds",
   "reviews", or "$" followed by a number.

4. **Save Page HTML** — Call `browser_evaluate` with:
   - `function`: `"() => document.documentElement.outerHTML"`
   - `filename`: `"search_page.html"`
   This saves rendered HTML to disk.  You receive a confirmation, NOT the HTML.

5. **Parse Search Results** — Call `parse_search_results(html_file="search_page.html")`
   to extract listings with preview data (title, price, rating, beds,
   bedrooms, bathrooms, URL).

6. **Pre-filter Search Results** — Call `filter_search_results(listings, constraints)`
   with a ``TripWeek`` to eliminate listings that clearly don't match
   (wrong neighbourhood, too few bedrooms, below min rating, over budget).
   **If the filter returns fewer than 3 listings**, proceed with the top 5
   unfiltered listings sorted by rating — do NOT spend turns deliberating
   on empty results.

7. **Explore Listings** — Call `explore_listings(urls, location, check_in,
   check_out, num_people, num_nights, search_listings, constraints)`:
   - **`search_listings`**: Pass the parsed search-card listings from Step 5
     to backfill fields (num_reviews, bathrooms, rating) that the listing
     detail page may not include.
   - **`constraints`**: Pass the ``TripWeek`` to get automatic constraint
     verification and categorical ranking built into the return value.
   When constraints are provided, returns an `ExplorationWithAnalysis` with:
   - `succeeded`: all explored `ListingWithCost` objects
   - `failed`: list of `ListingFailure` with `url` and `error`
   - `constraint_results`: per-listing pass/fail with violation reasons
   - `passed_listings`: only listings that satisfy all constraints
   - `rankings`: best pick per category (price, value, amenities, location, reviews)
   This eliminates the need for separate filter + rank calls.

8. **Present Results** — Summarise the exploration results to the user.
   If any listings failed, mention why briefly.  Show the rankings and
   highlight constraint violations for failed listings so the user
   understands why they were excluded.

9. **Multi-week Trip Totals** — For multi-week trips, use
    `calculate_trip_totals(week_analyses, participant_names)` to compute
    per-person totals across all weeks.

## File Naming Convention

When saving HTML via `browser_evaluate`, use:
- Search results: `"search_page.html"`
- Listing pages: `"listing_<room_id>.html"`
- Booking pages: `"booking_<room_id>.html"`

## HTML Bridge Pattern

Parser tools (`parse_search_results`, `parse_listing_details`,
`parse_booking_price`) require HTML saved to disk via `browser_evaluate` +
`filename`.  **Never** pass `browser_snapshot` output to parsers —
snapshots are YAML accessibility trees, not HTML.

## Error Handling

| Situation | Action |
|-----------|--------|
| Listing unavailable | Skip immediately, move to next |
| 404 / error page | Skip immediately, never retry same listing |
| Parsing failure | Log, skip, continue |
| 3 consecutive failures | STOP exploring, proceed to results |
| CAPTCHA / empty results | Inform user immediately |

**Never fabricate data** — only use URLs from `parse_search_results`.
**Never re-visit failed listings** — track attempted room IDs.
If you catch yourself writing "let me try" more than twice, STOP — you
are in a loop.  Proceed to results with whatever listings you have.

## Context Window Conservation

- **NEVER** call `browser_snapshot()` at any point during a trip planning
  session — a single Airbnb page snapshot is ~10K tokens of YAML
  accessibility tree data that provides NO useful information for listing
  analysis.  Every snapshot call wastes context and degrades performance.
  There is ZERO reason to call it: `browser_evaluate` with targeted
  JavaScript retrieves any data you need.
- `browser_click` requires a `ref` from `browser_snapshot`.  Inside listing
  exploration, use JavaScript click patterns via `browser_evaluate`.
- After completing each step, summarise intermediate results concisely
  (e.g. "Found 18 listings, 4 passed filter") instead of echoing raw
  tool output.  This prevents cumulative token inflation across 30+ turns.
- For multi-week trips, do NOT repeat prior-week results — reference them
  by listing title/ID.

## Progress Reporting

Report progress before each step: "**Step N/9: <description>**"
Report per-listing progress: "**Step 7/9: Exploring listing 3 of 5…**"
Report failures briefly: "**Step 7/9: Listing 3 returned 404, skipping…**"

## Parallel Tool Calls

Request multiple independent tool calls in a single turn to save round trips.

**Never batch browser tools** — they share a single browser instance and
must run sequentially.

## Code Mode (`run_code`)

When the `run_code` tool is available, the Airbnb-domain tools
(URL builders, parsers, `filter_search_results`, `explore_listings`,
`verify_constraints`, `rank_by_category`, `calculate_trip_totals`)
are accessible **only** from inside `run_code` — they are not exposed
as individual tool calls.  Browser tools (`browser_navigate`,
`browser_evaluate`, `browser_wait_for`, …) remain as normal tool calls
and **must not** be called from inside `run_code`.

Workflow with Code Mode:
1. Use browser tools normally for navigate / wait / save HTML.
2. Once HTML is on disk, call `run_code` once with a Python snippet
   that chains all the Airbnb-domain tools together — e.g. parse
   search results, filter, then explore the survivors with
   `await asyncio.gather(...)`, then rank.
3. The **last expression** of the snippet is automatically returned
   to you — no need to `print`.
4. REPL state (variables, imports) persists across `run_code` calls
   within the same agent run, so you can reference earlier results
   by variable name.

Example snippet:

```python
listings = await parse_search_results(html_file="search_page.html")
filtered = await filter_search_results(listings, constraints)
result = await explore_listings(
    urls=[l.url for l in filtered[:5]],
    location=location,
    check_in=check_in,
    check_out=check_out,
    num_people=num_people,
    num_nights=num_nights,
    search_listings=filtered,
    constraints=constraints,
)
result
```

This collapses 4+ model round-trips into one.  Use it whenever you
need to chain two or more Airbnb-domain tools.

## Guidelines

- Wait at least 5 seconds between Airbnb page loads.
- Present results with: title, nightly rate, total cost, cost per person,
  rating, reviews, key amenities.
- For multi-week trips, show per-person costs across weeks.
- Tool outputs are intermediate data — process and continue.  Only respond
  to user messages conversationally.
- Reuse data from conversation history to avoid redundant work.

"""

# TODO: Replace inline progress reporting with `pydantic-ai-todo` TodoCapability
# for structured real-time progress streaming to the frontend.  The event system
# (TodoEventEmitter.on_completed / on_created) can pipe task state changes through
# the SSE chat stream so the UI renders a live progress indicator instead of
# relying on the agent's text output.  See: https://github.com/vstorm-co/pydantic-ai-todo


# ── Playwright MCP Server ──

playwright_server: MCPServerStdio = MCPServerStdio(
	"npx",
	args=[
		f"@playwright/mcp@{settings.PLAYWRIGHT_MCP_VERSION}",
		f"--output-dir={settings.PLAYWRIGHT_OUTPUT_DIR}",
	],
)
"""Playwright MCP server running as a stdio subprocess.

Provides raw browser automation tools (navigate, click, type, snapshot,
screenshot).  The ``--output-dir`` flag directs ``browser_evaluate``
file outputs (e.g. saved HTML) to a known directory that the parser
tools can read from.  Lifecycle is managed via ``async with agent:``
in the FastAPI lifespan.
"""

# ── Ollama Model ──

# Custom httpx client with generous timeouts for local LLM streaming.
# Ollama can pause for extended periods between output chunks while
# processing tool results or reasoning internally (thinking-enabled
# models like qwen3.5).  The connect timeout is short since Ollama is
# local, but the read/write/pool timeouts are very generous.
_ollama_http_client: AsyncClient = AsyncClient(
	timeout=Timeout(
		connect=10.0,
		read=settings.OLLAMA_TIMEOUT,
		write=settings.OLLAMA_TIMEOUT,
		pool=settings.OLLAMA_TIMEOUT,
	),
	limits=Limits(
		max_connections=10,
		max_keepalive_connections=5,
		keepalive_expiry=300.0,
	),
)

model: OpenAIChatModel = OpenAIChatModel(
	settings.OLLAMA_MODEL_NAME,
	provider=OllamaProvider(
		base_url=f"{settings.OLLAMA_BASE_URL}/v1",
		http_client=_ollama_http_client,
	),
)
"""LLM model instance pointing to Ollama's OpenAI-compatible endpoint.

Uses a custom httpx client with generous timeouts and keepalive
settings to prevent mid-stream connection drops during long
agent runs with large contexts."""

# ── Custom Airbnb Toolset ──

AIRBNB_TOOLS_INSTRUCTIONS: str = """\
Airbnb-domain tools for URL construction, HTML parsing, filtering,
cost computation, and categorical ranking.

- **URL builders**: `build_search_url`, `build_listing_url`
  - `build_search_url` accepts pre-filter params: `min_bedrooms`,
    `min_bathrooms`, `min_beds`, `required_amenities`, `room_type`,
    `price_min`, `price_max` — pass these to reduce irrelevant results.
- **HTML parsers**: `parse_search_results`, `parse_listing_details`,
  `parse_booking_price`, `parse_listing_page` — accept `html_file`
  (filename from `browser_evaluate`) or `page_html` (raw string).
  Always use `html_file` in the normal workflow.
- **Pre-filter**: `filter_search_results` — lightweight filter on search
  preview data BEFORE exploration (neighbourhood, bedrooms, rating, budget).
  Optimistic: unknown data passes through.
- **Batch exploration**: `explore_listings` — opens listings in parallel
  browser instances so Airbnb renders pricing for the specified dates.
  Pass `search_listings` (from `parse_search_results`) to backfill fields
  like `num_reviews`, `num_bathrooms`, `rating` that the detail page may miss.
  Pass `constraints` (a `TripWeek`) to get automatic constraint verification
  and categorical ranking — returns `ExplorationWithAnalysis` with
  `constraint_results`, `passed_listings`, and `rankings` built in.
- **Constraint verification**: `verify_constraints` — checks each listing
  against trip week constraints with per-constraint pass/fail reasons.
  Normally called automatically by `explore_listings` when constraints
  are provided.
- **Analysis**: `rank_by_category`, `calculate_trip_totals`
"""


# Define and configure the Airbnb FunctionToolset with all domain-specific tools.
airbnb_toolset: FunctionToolset = FunctionToolset(
	[
		Tool(build_search_url, takes_ctx=False),
		Tool(build_listing_url, takes_ctx=False),
		Tool(parse_search_results, takes_ctx=False),
		Tool(parse_listing_details, takes_ctx=False),
		Tool(parse_booking_price, takes_ctx=False),
		Tool(parse_listing_page, takes_ctx=False),
		Tool(filter_search_results, takes_ctx=False),
		Tool(explore_listings, takes_ctx=False),
		Tool(verify_constraints, takes_ctx=False),
		Tool(calculate_trip_totals, takes_ctx=False),
		Tool(rank_by_category, takes_ctx=False),
	],
	instructions=AIRBNB_TOOLS_INSTRUCTIONS,
)
airbnb_toolset.__doc__ = """Custom FunctionToolset bundling all Airbnb-domain tools."""

"""Custom ``FunctionToolset`` bundling all Airbnb-domain tools."""


# ── Code Mode Capability (pydantic-ai-harness) ──
#
# When ``settings.CODE_MODE_ENABLED`` is True, the Airbnb FunctionToolset
# is tagged with ``code_mode=True`` metadata and a ``CodeMode`` capability
# is attached to the agent.
#
# At runtime, ``pydantic-ai-harness`` wrap every metadata-matched tool behind a single ``run_code`` tool powered
# by the Monty Python sandbox.  The model can then chain multiple Airbnb
# tool calls (loops, ``asyncio.gather``, in-memory filtering, last-expression
# return values) inside one model turn instead of paying one round-trip
# per call — a major win for the multi-listing exploration workflow.
#
# Browser/MCP tools are intentionally excluded:
#   * They share a single browser instance and must run sequentially.
#   * Deferred-execution / approval-required tools are excluded from the
#     sandbox by Code Mode anyway.
#
# Metadata-based selection is used so at toggling the feature only
# requires flipping the env var — no tool plumbing changes.
_airbnb_toolset_for_agent: Union[FunctionToolset, SetMetadataToolset] = (
	airbnb_toolset.with_metadata(code_mode=True)
	if settings.CODE_MODE_ENABLED
	else airbnb_toolset
)

# NOTE: ``CodeMode`` is wired in but disabled by default — the published
# ``pydantic-ai-harness 0.1.1`` calls ``FunctionSnapshot.resume(future=...)``
# which is not supported by any released ``pydantic-monty`` (latest 0.0.16
# only accepts ``resume(result, ...)``).  Enabling it causes every
# ``run_code`` invocation to raise ``TypeError``.  Flip
# ``CODE_MODE_ENABLED=true`` once upstream ships a compatible Monty.
_agent_capabilities: Union[list[AbstractCapability], None] = (
	[
		CodeMode(
			tools={
				"code_mode": True
			},  # Match tools with this metadata to wrap in run_code (the Airbnb toolset)
			max_retries=settings.CODE_MODE_MAX_RETRIES,
		)
	]
	if settings.CODE_MODE_ENABLED
	else []
)


# ── Agent ──

agent: Agent = Agent(
	model,
	toolsets=[playwright_server, _airbnb_toolset_for_agent],
	capabilities=_agent_capabilities,
	instructions=AGENT_INSTRUCTIONS,
	retries=2,
	model_settings=ModelSettings(
		max_tokens=settings.OLLAMA_MAX_TOKENS,
		temperature=settings.OLLAMA_TEMPERATURE,
		timeout=settings.OLLAMA_TIMEOUT,
		parallel_tool_calls=True,
		frequency_penalty=settings.OLLAMA_FREQUENCY_PENALTY,
		presence_penalty=settings.OLLAMA_PRESENCE_PENALTY,
		thinking="low",
	),
)
"""The central Pydantic AI agent for Airbnb search and general trip planning.

Combines the Playwright MCP browser toolset with custom Airbnb domain
tools.  When ``settings.CODE_MODE_ENABLED`` is True, the Airbnb tools
are exposed via a sandboxed ``run_code`` tool from
``pydantic-ai-harness`` so the model can orchestrate them with Python.
Configured with ``retries=2`` for resilience against transient
model failures.
"""


# ── Ollama Context Window Configuration ──
def _derive_model_name(base_model: str, num_ctx: int) -> str:
	"""Build a descriptive name for the derived Ollama model.

	Args:
		base_model: The base Ollama model name (e.g. ``"qwen3.5:35b-a3b"``).
		num_ctx: The context window size in tokens.

	Returns:
		A derived model name (e.g. ``"qwen3.5:35b-a3b-ctx32k"``).
	"""
	return f"{base_model}-ctx{num_ctx // 1024}k"


async def ensure_ollama_model(
	base_url: str,
	base_model: str,
	num_ctx: int,
) -> str:
	"""Ensure a derived Ollama model with the desired context size exists.

	Ollama's OpenAI-compatible ``/v1/chat/completions`` endpoint does **not**
	support the ``options.num_ctx`` parameter (it silently ignores it),
	meaining there's no way to set the context window size dynamically at request time.

	The official workaround is to create a derived model with ``num_ctx``
	baked into its configuration via Ollama's native ``/api/create`` endpoint.

	If the derived model already exists, this function is a no-op.

	Args:
		base_url: Ollama base URL (e.g. ``"http://localhost:11434"``).
		base_model: The base Ollama model name (e.g. ``"qwen3.5:35b-a3b"``).
		num_ctx: The context window size in tokens.

	Returns:
		The name of the derived model (e.g. ``"qwen3.5:35b-a3b-ctx32k"``).

	Raises:
		RuntimeError: If the base model is not found in Ollama.
		HTTPStatusError: If the Ollama API request fails.
	"""
	derived_name: str = _derive_model_name(base_model, num_ctx)

	async with AsyncClient(base_url=base_url, timeout=60.0) as client:
		# Check if derived model already exists
		resp: Response = await client.post("/api/show", json={"model": derived_name})
		if resp.status_code == 200:
			info(
				"Ollama model '{derived_name}' already exists.",
				derived_name=derived_name,
			)
			return derived_name

		# Verify base model is available
		resp: Response = await client.post("/api/show", json={"model": base_model})
		if resp.status_code != 200:
			raise RuntimeError(
				f"Base Ollama model '{base_model}' not found. "
				f"Pull it first: ollama pull {base_model}"
			)

		# Create derived model with custom num_ctx
		info(
			"Creating Ollama model '{derived_name}' (from '{base_model}', num_ctx={num_ctx})...",
			derived_name=derived_name,
			base_model=base_model,
			num_ctx=num_ctx,
		)
		resp: Response = await client.post(
			"/api/create",
			json={
				"model": derived_name,
				"from": base_model,
				"parameters": {"num_ctx": num_ctx},
				"stream": False,
			},
		)
		resp.raise_for_status()
		info(
			"Created Ollama model '{derived_name}' successfully.",
			derived_name=derived_name,
		)
		return derived_name


async def configure_agent_model() -> None:
	"""Ensure the derived Ollama model exists and update the agent.

	Creates a derived Ollama model with ``num_ctx`` from
	``settings.OLLAMA_NUM_CTX`` baked in (if it doesn't already exist),
	then updates the agent's model reference to use it.

	Must be called during application startup (e.g. FastAPI lifespan)
	before the agent processes any requests.
	"""
	derived_name: str = await ensure_ollama_model(
		base_url=settings.OLLAMA_BASE_URL,
		base_model=settings.OLLAMA_MODEL_NAME,
		num_ctx=settings.OLLAMA_NUM_CTX,
	)
	agent.model = OpenAIChatModel(
		derived_name,
		provider=OllamaProvider(
			base_url=f"{settings.OLLAMA_BASE_URL}/v1",
			http_client=_ollama_http_client,
		),
	)
	info("Agent model updated to '{derived_name}'.", derived_name=derived_name)


# ── Dev Chat UI (to_web) configuration ──
if settings.DEBUG and settings.ENVIRONMENT in ("development", "testing"):
	# Ensure the Playwright output directory exists before the MCP server starts.
	# In production the FastAPI lifespan handles this, but in dev mode the agent
	# may be run directly via to_web() which skips the FastAPI lifespan.
	Path(settings.PLAYWRIGHT_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

	# ── Ensure derived Ollama model for dev mode ──
	# The FastAPI lifespan calls configure_agent_model() async, but to_web()
	# bypasses the lifespan.  As a result, here we use httpx sync (since this needs to block until the model is ready)
	# and call the Ollama API directly via the client to create/verify the
	# derived model at module import time so the agent has the correct
	# context window when running via to_web().
	_derived_name: str = _derive_model_name(
		settings.OLLAMA_MODEL_NAME, settings.OLLAMA_NUM_CTX
	)
	try:
		with Client(base_url=settings.OLLAMA_BASE_URL, timeout=60.0) as _client:
			_resp: Response = _client.post("/api/show", json={"model": _derived_name})
			if _resp.status_code != 200:
				info(
					"Dev mode: creating derived model '{derived_name}'...",
					derived_name=_derived_name,
				)
				_client.post(
					"/api/create",
					json={
						"model": _derived_name,
						"from": settings.OLLAMA_MODEL_NAME,
						"parameters": {"num_ctx": settings.OLLAMA_NUM_CTX},
						"stream": False,
					},
					timeout=60.0,
				).raise_for_status()
		agent.model = OpenAIChatModel(
			_derived_name,
			provider=OllamaProvider(
				base_url=f"{settings.OLLAMA_BASE_URL}/v1",
				http_client=_ollama_http_client,
			),
		)
		info(
			"Dev mode: agent model set to '{derived_name}'.", derived_name=_derived_name
		)
	except Exception as exc:
		warning(
			"Could not create derived Ollama model '{derived_name}': {exc}. "
			"Using base model '{base_model}' (context window may be limited).",
			derived_name=_derived_name,
			exc=exc,
			base_model=settings.OLLAMA_MODEL_NAME,
		)

	web_chat_app: Union[Starlette, None] = agent.to_web() if settings.DEBUG else None

	instrument_starlette(web_chat_app) if web_chat_app else None
