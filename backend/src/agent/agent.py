"""Pydantic AI agent instance with Playwright MCP and custom Airbnb search tools.

Configures the central Pydantic AI agent (``agent harness``) that orchestrates Airbnb searches using a hybrid tool strategy:

1. **Playwright MCP toolset** — raw browser tools (navigate, click, snapshot)
   for interacting with Airbnb pages via a subprocess MCP server.
2. **Custom Airbnb toolset** — domain-specific ``FunctionToolset`` with URL
   builders, HTML parsers, cost computation, filtering, and ranking.

The agent uses ``qwen2.5:32b`` hosted on Ollama, accessed through Pydantic AI's
``OllamaProvider``.  Playwright MCP runs as a stdio subprocess managed by the
FastAPI lifespan (see ``src.main``).
"""

from typing import Union

from pydantic_ai import Agent, Tool
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

# ── System Instructions ──

AGENT_INSTRUCTIONS: str = """\
You are an expert Trip planner agent and Airbnb search specialist. Your task as Airbnb search specialist is to search Airbnb,
analyse listings, compute cost breakdowns, and recommend the best options
to the user.

## Workflow

Follow these steps when the user asks you to plan a trip or find Airbnb listings:

1. **Build Search URL** — Call `build_search_url(location, check_in, check_out,
   num_adults)` to construct a properly formatted Airbnb search URL for the
   given location and dates.

2. **Navigate to Search Page** — Use the browser MCP tools
   (`browser_navigate`) to load the search URL in the browser.

3. **Get Page Content** — Use `browser_snapshot` to capture the current page
   content as accessibility-tree text.

4. **Parse Search Results** — Pass the full page HTML to
   `parse_search_results(page_html)` to extract a list of available listings
   with preview data (title, price, rating, URL).

5. **Explore Promising Listings** — For the most promising listings (based on
   price, rating, or user preferences):
   a. Use `build_listing_url(room_id, check_in, check_out, num_adults)` or
      navigate directly to the listing URL from the search results.
   b. Use `browser_navigate` to load the listing page.
   c. Use `browser_snapshot` to get the page content.
   d. Call `parse_listing_details(page_html)` to extract full metadata
      (bedrooms, bathrooms, amenities, rating, reviews).

6. **Get Booking Price** — On each listing page, call
   `parse_booking_price(page_html)` to extract the total cost with fee
   breakdown (cleaning fee, service fee, taxes).

7. **Filter Listings** — Use `filter_listings(listings, constraints)` to
   narrow down listings that match the user's requirements (bedrooms,
   bathrooms, amenities, budget, neighbourhood preferences).

8. **Calculate Cost Breakdowns** — Use
   `calculate_cost_breakdown(total_cost, num_people, num_nights, fees)` to
   compute per-person and per-night costs for each qualifying listing.

9. **Rank by Category** — Use `rank_by_category(listings)` to identify the
   best listing in each category:
   - Best price (lowest total cost)
   - Best value (best cost-to-rating ratio)
   - Best amenities (most amenities)
   - Best location (has neighbourhood data)
   - Best reviews (highest rating)

10. **Multi-week Trip Totals** — For multi-week trips, use
    `calculate_trip_totals(week_analyses, participant_names)` to compute
    per-person totals across all weeks, accounting for variable participants.

## Progress Reporting

As you work through the steps above, **always report your progress** to the
user so they can follow along in real time.  Before starting each step, emit
a short status line in the format:

> **Step N/10: <description>**

For example:
- "**Step 1/10: Building search URL for Mexico City, Mar 15–22, 4 guests…**"
- "**Step 5/10: Exploring listing 3 of 7 — 'Sunny Loft in Roma Norte'…**"

When a step with sub-iterations (e.g. exploring multiple listings) is in
progress, report each iteration so the user sees movement:
- "**Step 5/10: Exploring listing 5 of 7 — 'Penthouse in Condesa'…**"
- "**Step 6/10: Getting booking price for listing 5 of 7…**"

If a step is skipped (e.g. no filtering needed because the user gave no
constraints), briefly note it:
- "**Step 7/10: Skipped — no filter constraints provided.**"

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
	args=[f"@playwright/mcp@{settings.PLAYWRIGHT_MCP_VERSION}"],
	tool_prefix="browser",
)
"""Playwright MCP server running as a stdio subprocess.

Provides raw browser automation tools (navigate, click, type, snapshot,
screenshot) prefixed with ``browser_`` to avoid naming conflicts with
custom tools.  Lifecycle is managed via ``async with agent:`` in the
FastAPI lifespan.
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
cost computation, and categorical ranking.  Use these tools instead sof trying
to parse Airbnb HTML yourself or compute costs manually.

- URL builders: `build_search_url`, `build_listing_url`
- HTML parsers: `parse_search_results`, `parse_listing_details`,
  `parse_booking_price`
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
)
"""The central Pydantic AI agent for Airbnb search and general trip planning.

Combines the Playwright MCP browser toolset with custom Airbnb domain
tools.  Configured with ``retries=2`` for resilience against transient
model failures.
"""

web_chat_app: Union[Starlette, None] = agent.to_web() if settings.DEBUG else None
