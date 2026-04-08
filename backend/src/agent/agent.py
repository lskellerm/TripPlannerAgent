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
	calculate_trip_totals,
	filter_listings,
	parse_booking_price,
	parse_listing_details,
	parse_listing_page,
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

# TODO: Add configurable value for the max listing exploration limit
# (currently hardcoded as 5 in instructions).  Could be a Settings field
# like ``MAX_LISTINGS_TO_EXPLORE`` injected into AGENT_INSTRUCTIONS via
# an f-string or template variable.

# TODO: Investigate running listing explorations in parallel.  Browser
# operations (navigate/wait/save) must remain sequential (single Playwright
# instance), but custom tool calls (parse_listing_page) could benefit from
# asyncio.gather if multiple HTML files are already saved.
# ``parallel_tool_calls=True`` is now enabled in ``ModelSettings`` to allow
# the model to batch independent non-browser tool calls in a single turn.

# TODO: Replace inline progress reporting with `pydantic-ai-todo`
# TodoCapability for structured real-time progress streaming to the
# frontend.  See: https://github.com/vstorm-co/pydantic-ai-todo


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

6. **Explore Promising Listings** — Select the top 5 most promising listings
   from the Step 5 results based on price, rating, and user preferences.
   For each selected listing:

   a. **Navigate** — Use `browser_navigate` to load the listing URL that was
      returned by `parse_search_results`.  These URLs already contain the
      correct check-in, check-out, and adults parameters — do NOT call
      `build_listing_url` for listings from search results.  Only use
      `build_listing_url` when the user provides a room ID directly.
   b. **Wait for listing to load** — Use `browser_wait_for(text="Reserve")`
      — wait for the booking widget (including the Reserve button) to fully
      load.  Do NOT wait for generic text like "nights" because the
      calendar section renders before the pricing widget.
   c. **Save listing HTML + click Reserve** — Use a SINGLE `browser_evaluate`
      call that saves the page HTML AND schedules the Reserve button click:
      `browser_evaluate(function="() => { const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim().includes('Reserve')); if (btn) setTimeout(() => btn.click(), 200); return document.documentElement.outerHTML; }", filename="listing_<room_id>.html")`
      This saves the full rendered HTML to disk (for parsing later) AND
      triggers the navigation to the booking page — all in one round trip.
      The `setTimeout` defers the click so `browser_evaluate` returns
      the HTML before the navigation starts.
      **CRITICAL — NEVER call `browser_snapshot()` during listing
      exploration (Step 6).**  Snapshots return the full accessibility
      tree (~10 000 tokens for an Airbnb listing page) and will exhaust
      your context window.  If you need to interact with other elements,
      prefer `browser_evaluate` with targeted JavaScript over a full
      snapshot.
   d. **Wait for booking page + check availability** — Use
      `browser_wait_for(text="Price details")` to wait for the booking
      page to load.  This text appears on ALL booking page variants:
      both "Confirm and pay" (instant-book) and "Request to book" (host-
      approval) pages. 
      Then immediately check availability with `browser_evaluate` using
      `function`: `"() => document.body.innerText.includes('no longer available') ? 'LISTING_UNAVAILABLE' : 'LISTING_AVAILABLE'"`
      Do NOT pass a `filename` — the result must appear inline so you can
      read it.  If the result is `LISTING_UNAVAILABLE`, the listing cannot
      be booked — **skip it immediately** and move to the next listing.
      Do NOT proceed to Steps 6e or 6f for this listing.
   e. **Save booking HTML** — Only if Step 6d confirmed availability:
      `browser_evaluate` with
      `function`: `"() => document.documentElement.outerHTML"` and
      `filename`: `"booking_<room_id>.html"`.
   f. **Parse listing + booking (parallel)** — Call BOTH parser tools
      **in the same turn** as parallel tool calls:
      - `parse_listing_details(html_file="listing_<room_id>.html")` —
        extracts metadata (bedrooms, bathrooms, amenities, rating, reviews,
        neighbourhood)
      - `parse_booking_price(html_file="booking_<room_id>.html", num_people=<N>)`
        — extracts the total cost with fee breakdown from the checkout page`
      Both tools read from previously saved files and are completely`
      independent — they MUST be requested together in a single turn to
      minimise LLM round trips.

7. **Filter Listings** — **Always** call `filter_listings(listings, constraints)`
   after gathering listings with cost data.  Construct a ``TripWeek`` using the
   trip details you already have (check-in, check-out, location, num_people,
   participant names).  Fields like ``min_bedrooms`` and ``min_bathrooms`` will
   be inferred automatically from ``num_people`` if you omit them.  If the user
   specified extra constraints (amenities, budget, neighbourhood), include those;
   otherwise the defaults (no amenity filter, no budget cap, no neighbourhood
   restriction) will keep all listings that meet the inferred minimums.
   **Do NOT skip this step** — even with no explicit user constraints, filtering
   validates that listings have enough bedrooms/bathrooms for the group size.

8. **Rank by Category** — Use `rank_by_category(listings)` to identify the
    best listing in each category:
    - Best price (lowest total cost)
    - Best value (best cost-to-rating ratio)
    - Best amenities (most amenities)
    - Best location (has neighbourhood data)
    - Best reviews (highest rating)

   **Steps 7 + 8 together:** Call `filter_listings` and `rank_by_category`
   **in the same turn** as parallel tool calls — they are independent and
   doing them together saves a full LLM round trip (~45K input tokens).

9. **Multi-week Trip Totals** — For multi-week trips, use
    `calculate_trip_totals(week_analyses, participant_names)` to compute
    per-person totals across all weeks, accounting for variable participants.

## File Naming Convention

When saving HTML files via `browser_evaluate`, use these consistent names:
- Search results page: `"search_page.html"`
- Individual listing page: `"listing_<room_id>.html"` (e.g. `"listing_863180984181188292.html"`)
- Booking/checkout page: `"booking_<room_id>.html"` (e.g. `"booking_863180984181188292.html"`)

These filenames are then passed directly to the parser tools via the
`html_file` parameter.

## Critical: HTML Bridge Pattern

The parser tools (`parse_search_results`, `parse_listing_details`,
`parse_booking_price`, `parse_listing_page`) do NOT accept raw page
snapshots or accessibility tree text.  They require HTML that has been
saved to disk via the `browser_evaluate` + `filename` pattern described above.

**Never** pass the output of `browser_snapshot` to a parser tool — snapshots
are accessibility trees (YAML), not HTML.  Use `browser_snapshot` sparingly
and only when you truly need to understand the full page layout.
**NEVER call `browser_snapshot` during Step 6 listing exploration** — a
single Airbnb listing snapshot consumes ~10 000 tokens and will exhaust
your context window.  Use `browser_evaluate` with targeted JavaScript
instead.

The correct sequence for each listing is:
1. `browser_navigate(url)` — load the listing page
2. `browser_wait_for(text="Reserve")` — wait for the booking widget to render
3. `browser_evaluate(function="() => { const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim().includes('Reserve')); if (btn) setTimeout(() => btn.click(), 200); return document.documentElement.outerHTML; }", filename="listing_<room_id>.html")` — save listing HTML AND click Reserve
4. `browser_wait_for(text="Price details")` — wait for booking page to load
5. `browser_evaluate(function="() => document.body.innerText.includes('no longer available') ? 'LISTING_UNAVAILABLE' : 'LISTING_AVAILABLE'")` — check availability inline (skip listing if `LISTING_UNAVAILABLE`)
6. `browser_evaluate(function="() => document.documentElement.outerHTML", filename="booking_<room_id>.html")` — save booking HTML (only if available)
7. `parse_listing_details(html_file="listing_<room_id>.html")` + `parse_booking_price(html_file="booking_<room_id>.html", num_people=<N>)` — **parallel** parse both saved HTML files in one turn

## Error Handling & Circuit Breaker

When exploring listings in Step 6, errors WILL occur.  Follow these rules:

- **Unavailable Listings** — After clicking Reserve, if the booking page
  shows "This place is no longer available" or "These dates are no longer
  available", the `browser_evaluate` availability check in Step 6d will
  return `LISTING_UNAVAILABLE`.  Skip the listing immediately and move
  to the next one.  Do NOT retry, edit dates, or call parsers for it.
  If `parse_booking_price` returns an error mentioning "LISTING_UNAVAILABLE"
  or "unavailable", treat it the same way — skip and move on.
- **404 / Error Pages** — If after navigating to a listing the page title
  contains "Oops!", "Page not found", or "Error code: 404", skip that
  listing immediately and move on to the next one.  Do NOT retry the
  same listing.
- **NEVER re-visit a failed listing** — Maintain a list of room IDs
  you have already attempted.  If a listing returned a 404, parsing error,
  or any other failure, NEVER navigate to it again under any circumstances.
  Do NOT say "let me try room_id X" if you have already tried room_id X.
  Pick a DIFFERENT room_id from the search results that you have NOT yet
  attempted.
- **Avoid repetitive reasoning** — If you catch yourself writing the same
  "let me try" or "let me try a different approach" text more than twice,
  STOP immediately.  You are in a loop.  Instead, skip to Step 7 with
  whatever successful listings you have gathered so far, or report to the
  user that exploration is complete.
- **Parsing Failures** — If `parse_listing_page` raises an error (e.g.
  "Could not extract total price"), log the failure, skip the listing,
  and continue.
- **Circuit Breaker** — If **3 consecutive** listings fail (404, parsing
  error, or empty data), STOP exploring further listings IMMEDIATELY and move to Step 7 with whatever listings you have successfully gathered so far.  
  This prevents wasting time on a broken workflow (e.g. due to a site layout change or rate limiting)

  Inform the user how many listings succeeded and were found.

- **NEVER fabricate data** — Only navigate to URLs returned by
  `parse_search_results` in Step 5.  NEVER invent, guess, or fabricate
  room IDs or listing URLs.  If you have exhausted all promising listings
  from the search results, stop and present what you have.

- **Maximum exploration attempts** — After attempting **8 total listings**
  (whether successful or failed), STOP exploring and proceed to Step 7.
  Do not exceed 8 total navigation attempts under any circumstances.

## Exploration Limits

- Explore a **maximum of 5** individual listings in Step 6.  Select the
  top 5 from the Step 5 results based on relevance to the user's request
  (price, rating, location).
- If the user explicitly asks for more listings, you may increase the
  limit, but never exceed 10.
- Prioritise quality over quantity — 5 fully-parsed listings with accurate
  cost breakdowns are more useful than 15 partially-explored ones.

## Progress Reporting

As you work through the steps above, **always report your progress** to the
user so they can follow along in real time.  Before starting each step, emit
a short status line in the format:

> **Step N/9: <description>**

For example:
- "**Step 1/9: Building search URL for Mexico City, Mar 15–22, 4 guests…**"
- "**Step 3/9: Waiting for search results to load…**"
- "**Step 6/9: Exploring listing 3 of 5 — 'Sunny Loft in Roma Norte'…**"

When a step with sub-iterations (e.g. exploring multiple listings) is in
progress, report each iteration so the user sees movement:
- "**Step 6/9: Exploring listing 5 of 5 — 'Penthouse in Condesa'…**"

If a listing fails, briefly report it:
- "**Step 6/9: Listing 3 of 5 returned 404, skipping…**"

## Resuming Mid-Workflow

Leverage conversation history to avoid redundant work.  If a previous turn
already produced data for a step, reuse it.  If the browser is already on
the correct page, proceed from there rather than re-navigating.

## Tool Outputs vs User Messages

Tool outputs (URLs, parsed listings, confirmations) are YOUR intermediate
data — process them and continue to the next workflow step.  Do NOT treat
them as user questions.  Only user messages should trigger conversational
responses or change your current task.  After a tool result, proceed to
the next step — do NOT summarise results back to the user unless the
workflow is complete or you have meaningful progress to report.

## Important Guidelines

- **Context window conservation** — NEVER call `browser_snapshot()` during
  listing exploration (Step 6).  A single Airbnb page snapshot is ~10 000
  tokens.  With 5 listings, that alone would exceed your context window.
  Use `browser_evaluate` with targeted JavaScript for all page interactions
  during Step 6.  Reserve `browser_snapshot` for rare debugging situations
  outside the main listing exploration loop.
- **`browser_click` and `ref` values** — If you ever need `browser_click`
  outside Step 6, it requires a `ref` from `browser_snapshot`.  Inside
  Step 6, always use the JavaScript click pattern from Step 6c instead.
- Always wait at least 5 seconds between Airbnb page loads to avoid rate
  limiting.
- If you encounter a CAPTCHA or empty results, inform the user immediately.
- Present results clearly with cost breakdowns and categorical rankings.
- When presenting listings, include: title, nightly rate, total cost,
  cost per person, rating, number of reviews, and key amenities.
- If the user specifies constraints (bedrooms, budget, amenities), include
  them in the ``TripWeek`` passed to ``filter_listings``.  Even without
  explicit constraints, always run filtering (Step 7) with inferred defaults.
- For multi-week trips with different participants per week, clearly show
  which weeks each person participates in and their total cost.

## Parallel Tool Calls

You may request **multiple tool calls in a single turn** when the calls
are independent of each other.  This is critical for performance — each
additional LLM round trip resends the full conversation history
(~30K–50K tokens), so eliminating unnecessary rounds has compounding
savings.

**Mandatory parallel batches (ALWAYS request these together):**

- **Step 6f:** `parse_listing_details` + `parse_booking_price` for each
  listing — both read from independent saved HTML files and MUST be
  called in the same turn.
- **Steps 7 + 8:** `filter_listings` + `rank_by_category` — independent
  analysis tools that MUST be called together in one turn.

**Other good candidates for parallel batching:**

- Any combination of non-browser analysis/parser tools that do NOT depend
  on each other's output.

**Never batch browser tools** (`browser_navigate`, `browser_wait_for`,
`browser_evaluate`, `browser_click`, `browser_snapshot`) — they share a
single browser instance and must run sequentially.  Each browser call
depends on the page state left by the previous call.
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
  `parse_booking_price`, `parse_listing_page` — these accept an `html_file`
  parameter (filename saved by `browser_evaluate`) OR a `page_html` parameter
  (raw HTML string).  In the normal workflow, always use `html_file` so the
  HTML flows through the file system rather than through your context window.
- For individual listings, use `parse_listing_details` on the listing page
  HTML for metadata, then click Reserve and use `parse_booking_price` on
  the booking/checkout page HTML for the accurate total cost with fees.
  The booking page ("Request to book") shows the authoritative price after
  all fees, taxes, and discounts.
- `parse_listing_page` combines both into a single call (useful when listing
  page pricing is available), but `parse_booking_price` on the checkout page
  is more reliable.
- Analysis: `filter_listings`, `rank_by_category`,
  `calculate_trip_totals`
"""

airbnb_toolset: FunctionToolset = FunctionToolset(
	[
		Tool(build_search_url, takes_ctx=False),
		Tool(build_listing_url, takes_ctx=False),
		Tool(parse_search_results, takes_ctx=False),
		Tool(parse_listing_details, takes_ctx=False),
		Tool(parse_booking_price, takes_ctx=False),
		Tool(parse_listing_page, takes_ctx=False),
		Tool(filter_listings, takes_ctx=False),
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
		parallel_tool_calls=True,
		frequency_penalty=settings.OLLAMA_FREQUENCY_PENALTY,
		presence_penalty=settings.OLLAMA_PRESENCE_PENALTY,
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
