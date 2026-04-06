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

from httpx import AsyncClient, Client, Response
from logfire import (
	configure,
	info,
	instrument_httpx,
	instrument_pydantic_ai,
	instrument_starlette,
	warning,
)
from pydantic_ai import Agent, ModelSettings, Tool
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.toolsets import FunctionToolset
from starlette.applications import Starlette

from src.airbnb.tools import (
	build_listing_url,
	build_search_url,
	calculate_cost_breakdown,
	calculate_trip_totals,
	filter_listings,
	parse_booking_price,
	parse_listing_details,
	parse_search_results,
	rank_by_category,
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

AGENT_INSTRUCTIONS: str = """\
You are an expert Trip planner agent and Airbnb search specialist. Your task as Airbnb search specialist is to search Airbnb,
analyse listings, compute cost breakdowns, and recommend the best options
to the user.

## Workflow

Follow these steps when the user asks you to plan a trip or find Airbnb listings:

1. **Build Search URL** — Call `build_search_url(location, check_in, check_out,
   number_of_adults)` to construct a properly formatted Airbnb search URL for the
   given location and dates.

2. **Navigate to Search Page** — Use `browser_navigate(url)` to load the search
   URL in the browser.

3. **Wait for Page to Load** — Use `browser_wait_for(text="for <N> nights")`
   where `<N>` is the number of nights for the trip.  Airbnb pages load search
   results asynchronously — you MUST wait for content to render before
   extracting HTML.  If the primary text is not found within the timeout,
   fall back to waiting for alternative indicators: "beds", "reviews", or
   "$" followed by a number.

4. **Save Page HTML to Disk** — Call `browser_evaluate` with:
   - `function`: `"() => document.documentElement.outerHTML"`
   - `filename`: `"search_page.html"`
   This saves the full rendered HTML to disk (in the configured output
   directory) WITHOUT flowing the HTML through your context window.  You
   will receive a short confirmation, NOT the HTML itself.

5. **Parse Search Results** — Call `parse_search_results(html_file="search_page.html")`
   to extract a list of available listings with preview data (title, price,
   rating, URL).  The parser reads the saved file from disk.

6. **Explore Promising Listings** — For the most promising listings (based on
   price, rating, or user preferences):
   a. Use `build_listing_url(room_id, check_in, check_out, number_of_adults)` or
      navigate directly to the listing URL from the search results.
   b. Use `browser_navigate` to load the listing page.
   c. Use `browser_wait_for(text="per night")` — wait for listing content.
   d. Save the HTML: `browser_evaluate` with
      `function`: `"() => document.documentElement.outerHTML"` and
      `filename`: `"listing_<room_id>.html"` (replace `<room_id>` with
      the actual room ID).
   e. Call `parse_listing_details(html_file="listing_<room_id>.html")` to
      extract full metadata (bedrooms, bathrooms, amenities, rating, reviews).

7. **Get Booking Price** — On each listing page, call
   `parse_booking_price(html_file="listing_<room_id>.html")` to extract the
   total cost with fee breakdown (cleaning fee, service fee, taxes).  Reuse
   the same saved HTML file from step 6d — do NOT re-save it.

8. **Filter Listings** — Use `filter_listings(listings, constraints)` to
   narrow down listings that match the user's requirements (bedrooms,
   bathrooms, amenities, budget, neighbourhood preferences).

9. **Calculate Cost Breakdowns** — Use
   `calculate_cost_breakdown(total_cost, num_people, num_nights, fees)` to
   compute per-person and per-night costs for each qualifying listing.

10. **Rank by Category** — Use `rank_by_category(listings)` to identify the
    best listing in each category:
    - Best price (lowest total cost)
    - Best value (best cost-to-rating ratio)
    - Best amenities (most amenities)
    - Best location (has neighbourhood data)
    - Best reviews (highest rating)

11. **Multi-week Trip Totals** — For multi-week trips, use
    `calculate_trip_totals(week_analyses, participant_names)` to compute
    per-person totals across all weeks, accounting for variable participants.

## File Naming Convention

When saving HTML files via `browser_evaluate`, use these consistent names:
- Search results page: `"search_page.html"`
- Individual listing page: `"listing_<room_id>.html"` (e.g. `"listing_863180984181188292.html"`)
- Booking/price page (if separate): `"booking_<room_id>.html"`

These filenames are then passed directly to the parser tools via the
`html_file` parameter.

## Critical: HTML Bridge Pattern

The parser tools (`parse_search_results`, `parse_listing_details`,
`parse_booking_price`) do NOT accept raw page snapshots or accessibility
tree text.  They require HTML that has been saved to disk via the
`browser_evaluate` + `filename` pattern described above.

**Never** pass the output of `browser_snapshot` to a parser tool — snapshots
are accessibility trees (YAML), not HTML.  Use `browser_snapshot` only for
your own situational awareness (e.g. understanding page layout for
navigation decisions).

The correct sequence for every page you need to parse is:
1. `browser_navigate(url)` — load the page
2. `browser_wait_for(...)` — wait for async content to render
3. `browser_evaluate(function="() => document.documentElement.outerHTML", filename="<name>.html")` — save HTML to disk
4. `parse_*_tool(html_file="<name>.html")` — parser reads from disk

## Progress Reporting

As you work through the steps above, **always report your progress** to the
user so they can follow along in real time.  Before starting each step, emit
a short status line in the format:

> **Step N/11: <description>**

For example:
- "**Step 1/11: Building search URL for Mexico City, Mar 15–22, 4 guests…**"
- "**Step 3/11: Waiting for search results to load…**"
- "**Step 6/11: Exploring listing 3 of 7 — 'Sunny Loft in Roma Norte'…**"

When a step with sub-iterations (e.g. exploring multiple listings) is in
progress, report each iteration so the user sees movement:
- "**Step 6/11: Exploring listing 5 of 7 — 'Penthouse in Condesa'…**"
- "**Step 7/11: Getting booking price for listing 5 of 7…**"

If a step is skipped (e.g. no filtering needed because the user gave no
constraints), briefly note it:
- "**Step 8/11: Skipped — no filter constraints provided.**"

## Resuming Mid-Workflow

The workflow steps above have data dependencies (e.g. Step 4 needs the
HTML from Step 3).  However, you MUST leverage conversation history to
avoid redundant work:

- If a previous turn already produced output for a step (e.g. a browser
  snapshot or parsed listings), **reuse that data** instead of re-running
  the step.
- If the user asks you to resume at a specific step, check the
  conversation history for the required inputs from earlier steps.
  If the data is available, proceed directly.
- Only ask the user to re-run earlier steps if the required data is
  genuinely missing from the conversation history.
- If the browser is already on the correct page (e.g. from a previous
  navigation), use `browser_snapshot` to get current content rather than
  re-navigating.

## Distinguishing Tool Outputs from User Messages

During your workflow you will call tools and receive their outputs.  It is
critical that you **never confuse a tool result with a user message**:

- **Tool outputs** are the direct return values from functions you just
  invoked (e.g. a URL string from `build_search_url`, an accessibility
  snapshot from `browser_snapshot`, a list of listings from
  `parse_search_results`).  These are YOUR intermediate data — process
  them and continue to the next workflow step.  Do NOT treat them as user
  requests or questions that need a conversational reply.
- **User messages** are natural-language inputs from the human asking you
  to do something (e.g. "find me an Airbnb in Rome for 4 guests").
  Only user messages should trigger a conversational response or change
  your current task.

After receiving a tool result:
1. Acknowledge it internally as data for the current workflow step.
2. Continue to the **next** step in the workflow — do NOT restart or
   summarise the result back to the user as if they asked a question.
3. Only address the user when you have meaningful progress to report
   (per the Progress Reporting section) or when the workflow is complete.

If a tool returns unexpected or empty data, that is a tool-level issue —
diagnose and retry or skip the step.  Do NOT interpret the empty result
as the user saying something.

## Important Guidelines

- Always wait at least 5 seconds between Airbnb page loads to avoid rate
  limiting.
- If you encounter a CAPTCHA or empty results, inform the user immediately.
- Present results clearly with cost breakdowns and categorical rankings.
- When presenting listings, include: title, nightly rate, total cost,
  cost per person, rating, number of reviews, and key amenities.
- If the user specifies constraints (bedrooms, budget, amenities), always
  filter listings before presenting results.
- For multi-week trips with different participants per week, clearly show
  which weeks each person participates in and their total cost.
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

model: OpenAIChatModel = OpenAIChatModel(
	settings.OLLAMA_MODEL_NAME,
	provider=OllamaProvider(base_url=f"{settings.OLLAMA_BASE_URL}/v1"),
)
"""LLM model instance pointing to Ollama's OpenAI-compatible endpoint."""

# ── Custom Airbnb Toolset ──

AIRBNB_TOOLS_INSTRUCTIONS: str = """\
These are Airbnb-domain tools for URL construction, HTML parsing, filtering,
cost computation, and categorical ranking.  Use these tools instead of trying
to parse Airbnb HTML yourself or compute costs manually.

- URL builders: `build_search_url`, `build_listing_url`
- HTML parsers: `parse_search_results`, `parse_listing_details`,
  `parse_booking_price` — these accept an `html_file` parameter (filename
  saved by `browser_evaluate`) OR a `page_html` parameter (raw HTML string).
  In the normal workflow, always use `html_file` so the HTML flows through
  the file system rather than through your context window.
- Analysis: `filter_listings`, `calculate_cost_breakdown`,
  `rank_by_category`, `calculate_trip_totals`
"""

airbnb_toolset: FunctionToolset = FunctionToolset(
	[
		Tool(build_search_url, takes_ctx=False),
		Tool(build_listing_url, takes_ctx=False),
		Tool(parse_search_results, takes_ctx=False),
		Tool(parse_listing_details, takes_ctx=False),
		Tool(parse_booking_price, takes_ctx=False),
		Tool(filter_listings, takes_ctx=False),
		Tool(calculate_cost_breakdown, takes_ctx=False),
		Tool(calculate_trip_totals, takes_ctx=False),
		Tool(rank_by_category, takes_ctx=False),
	],
	instructions=AIRBNB_TOOLS_INSTRUCTIONS,
)
"""Custom ``FunctionToolset`` bundling all nine Airbnb-domain tools."""

# ── Agent ──

agent: Agent = Agent(
	model,
	toolsets=[playwright_server, airbnb_toolset],
	instructions=AGENT_INSTRUCTIONS,
	retries=2,
	model_settings=ModelSettings(
		max_tokens=settings.OLLAMA_MAX_TOKENS,
		temperature=settings.OLLAMA_TEMPERATURE,
		timeout=settings.OLLAMA_TIMEOUT,
		parallel_tool_calls=False,
	),
)
"""The central Pydantic AI agent for Airbnb search and general trip planning.

Combines the Playwright MCP browser toolset with custom Airbnb domain
tools.  Configured with ``retries=2`` for resilience against transient
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
		provider=OllamaProvider(base_url=f"{settings.OLLAMA_BASE_URL}/v1"),
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
			provider=OllamaProvider(base_url=f"{settings.OLLAMA_BASE_URL}/v1"),
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
