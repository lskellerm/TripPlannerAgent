"""Batch listing exploration via parallel Playwright browser instances.

Provides :func:`explore_listings` which takes a list of Airbnb listing
URLs and concurrently navigates to each one using independent Playwright
browser contexts — extracting listing details and booking prices in a
single pass per listing (merged availability check + booking save from
Solution 2).

This replaces the agent's serial MCP-driven exploration loop with a
deterministic, parallel Python function that eliminates ~4 agent round
trips per listing.
"""

import asyncio
import re
from types import CoroutineType
from typing import Any, Union
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse

from logfire import info, warning
from playwright.async_api import (
	Browser,
	BrowserContext,
	Page,
	async_playwright,
)

from src.agent.schemas import TripWeek
from src.airbnb.constants import (
	BOOKING_CONFIRM_PAY_SELECTOR,
	BOOKING_PRICE_DETAILS_SELECTOR,
	BOOKING_TOTAL_SELECTOR,
	LISTING_BOOKING_SIDEBAR_SELECTOR,
	RESERVE_BUTTON_SELECTOR,
)
from src.airbnb.schemas import (
	AirbnbListing,
	ConstraintResult,
	CostBreakdown,
	ExplorationResult,
	ExplorationWithAnalysis,
	ListingFailure,
	ListingWithCost,
)
from src.airbnb.tools.parsers import parse_booking_price, parse_listing_details
from src.core.config import settings

__all__: list[str] = [
	"explore_listings",
]

# Minimum delay between page loads to respect Airbnb rate limits (seconds).
_PAGE_LOAD_DELAY: float = 2.0


async def _safe_page_title(page: Page) -> str:
	"""Get page title without raising.

	Args:
		page: Playwright page.

	Returns:
		Page title when available, otherwise a placeholder string.
	"""
	try:
		return await page.title()
	except Exception:
		return "<unknown>"


async def _log_booking_page_state(page: Page, full_url: str, stage: str) -> None:
	"""Log lightweight booking-page diagnostics.

	Args:
		page: Playwright page currently in use.
		full_url: Listing URL with date params.
		stage: Human-readable stage label for diagnostics.
	"""
	has_total: bool = False
	has_price_details: bool = False
	has_confirm_pay: bool = False
	has_reserve_button: bool = False

	try:
		has_total: bool = await page.locator(BOOKING_TOTAL_SELECTOR).count() > 0
		has_price_details: bool = (
			await page.locator(BOOKING_PRICE_DETAILS_SELECTOR).count() > 0
		)
		has_confirm_pay: bool = (
			await page.locator(BOOKING_CONFIRM_PAY_SELECTOR).count() > 0
		)
		has_reserve_button: bool = (
			await page.locator(RESERVE_BUTTON_SELECTOR).count() > 0
		)
	except Exception:
		# Best-effort diagnostics only.
		pass

	info(
		"Booking page state ({stage}) for {url}: page_url={page_url}, title={title}, has_total={has_total}, has_price_details={has_price_details}, has_confirm_pay={has_confirm_pay}, has_reserve_button={has_reserve_button}",
		stage=stage,
		url=full_url,
		page_url=page.url,
		title=await _safe_page_title(page),
		has_total=has_total,
		has_price_details=has_price_details,
		has_confirm_pay=has_confirm_pay,
		has_reserve_button=has_reserve_button,
	)


async def _wait_for_booking_page_ready(page: Page, full_url: str) -> bool:
	"""Wait for booking page readiness signals after clicking Reserve.

	This function helps control the timing uncertainty around when the booking page is ready for price parsing after clicking the Reserve button.

	It waits for multiple possible signals of booking page readiness, including URL transitions and the presence of key booking-related selectors in the DOM.

	 If these signals do not appear within expected timeouts, it logs a warning and returns False, allowing the agent to proceed with whatever content is available (which may lead to a parsing failure that is handled gracefully).

	Args:
		page: Playwright page to observe.
		full_url: Listing URL with date params.

	Returns:
		True when booking signals are detected, False on timeout.
	"""
	# Give navigation/rendering a chance to start.
	try:
		await page.wait_for_load_state("domcontentloaded", timeout=7000)
	except Exception:
		pass

	# Fast-path: total selector already present.
	if await page.locator(BOOKING_TOTAL_SELECTOR).count() > 0:
		info("Booking total selector already present for {url}", url=full_url)
		await _log_booking_page_state(page, full_url, stage="ready-immediate")
		return True

	# Prefer URL transition when Airbnb pushes to checkout path, checking the URL for /book/ which is a strong signal of booking flow.
	try:
		await page.wait_for_url(re.compile(r".*/book/.*"), timeout=12000)
		# Once the frame transitions to /book/, treat the page as ready and skip fallback DOM probing.
		try:
			await page.wait_for_load_state("domcontentloaded", timeout=7000)
		except Exception:
			pass
		info(
			"Booking URL transition detected for {url}: {page_url}",
			url=full_url,
			page_url=page.url,
		)
		await _log_booking_page_state(page, full_url, stage="ready-url-transition")
		return True
	except Exception:
		info(
			"No /book/ URL transition detected for {url}; checking fallback page signals",
			url=full_url,
		)

	# Fallback to semantic booking-page signals in body text/DOM.
	try:
		await page.wait_for_function(
			f"""() => Boolean(
				document.querySelector('{BOOKING_TOTAL_SELECTOR}') ||
				(document.body?.innerText || "").toLowerCase().includes("price details") ||
				(document.body?.innerText || "").toLowerCase().includes("confirm and pay")
			)""",
			timeout=20000,
		)
		await _log_booking_page_state(page, full_url, stage="ready-signals")
		return True
	except Exception:
		warning(
			"Booking page readiness signals timed out for {url}; proceeding with available content",
			url=full_url,
		)
		await _log_booking_page_state(page, full_url, stage="timeout")
		return False


async def _wait_for_listing_booking_widget_ready(page: Page, full_url: str) -> None:
	"""Wait for listing-page booking widget signals before clicking Reserve.

	Args:
		page: Playwright page to observe.
		full_url: Listing URL with date params.
	"""
	try:
		await page.wait_for_selector(LISTING_BOOKING_SIDEBAR_SELECTOR, timeout=8000)
		info("Listing booking sidebar loaded for {url}", url=full_url)
		return
	except Exception:
		info(
			"Listing booking sidebar selector not found for {url}; checking Reserve button",
			url=full_url,
		)

	try:
		await page.wait_for_selector(RESERVE_BUTTON_SELECTOR, timeout=5000)
		info("Reserve button loaded for {url}", url=full_url)
		return
	except Exception:
		info(
			"Reserve button selector not found for {url}; waiting for price text",
			url=full_url,
		)

	try:
		await page.wait_for_selector(
			"text=/\\$[\\d,]+\\s*(x|×|for)\\s*\\d+\\s*night/i",
			timeout=5000,
		)
		info("Price text loaded for {url}", url=full_url)
	except Exception:
		warning(
			"Listing booking widget waits timed out for {url}; proceeding with available content",
			url=full_url,
		)


def _ensure_date_params(
	url: str,
	check_in: str,
	check_out: str,
	num_adults: int,
) -> str:
	"""Ensure a listing URL includes check-in/check-out query params.

	Airbnb listing pages only show pricing when the URL contains date
	and guest parameters.  Without them the page shows "Add dates for
	prices" and ``parse_booking_price`` will fail.

	If the URL already contains ``check_in`` and ``check_out`` params
	they are preserved.  Otherwise the supplied values are appended.

	Args:
		url: Airbnb listing URL (with or without query params).
		check_in: Check-in date (``YYYY-MM-DD``).
		check_out: Check-out date (``YYYY-MM-DD``).
		num_adults: Number of adult guests.

	Returns:
		The URL with ``check_in``, ``check_out``, and ``adults``
		params guaranteed to be present.
	"""
	parsed: ParseResult = urlparse(url)
	existing_params: dict[str, list[str]] = parse_qs(parsed.query)

	if "check_in" not in existing_params:
		existing_params["check_in"] = [check_in]
	if "check_out" not in existing_params:
		existing_params["check_out"] = [check_out]
	if "adults" not in existing_params:
		existing_params["adults"] = [str(num_adults)]

	# Flatten single-value lists for urlencode
	flat_params: dict[str, str] = {
		k: v[0] if isinstance(v, list) else v for k, v in existing_params.items()
	}
	new_query: str = urlencode(flat_params)
	return urlunparse(parsed._replace(query=new_query))


async def _explore_single_listing(
	browser: Browser,
	url: str,
	location: str,
	check_in: str,
	check_out: str,
	num_people: int,
	num_nights: int,
	search_listing: Union[AirbnbListing, None] = None,
) -> Union[ListingWithCost, ListingFailure]:
	"""Explore a single listing via its listing page and booking page.

	Two-page strategy:

	1. **Listing page** — Navigate to the listing URL (with date/guest
	   query params), wait for the booking sidebar to hydrate, then
	   capture the HTML and parse listing details (title, amenities,
	   ratings, etc.) via :func:`parse_listing_details`.

	2. **Booking page** — Click the "Reserve" button
	   (``data-testid="homes-pdp-cta-btn"``) to navigate to Airbnb's
	   "Confirm and pay" checkout page, wait for the price breakdown
	   to render (``data-testid="pd-value-TOTAL"``), capture the HTML,
	   and parse the total cost via :func:`parse_booking_price`.

	After both pages are parsed, any fields missing from the listing
	detail page are backfilled from ``search_listing`` (the
	search-card data) — e.g. ``num_reviews``, ``num_bathrooms``,
	``rating``.  The ``nightly_rate`` is computed from the cost
	breakdown if it was not extracted from either source.

	Args:
		browser: Shared Playwright browser instance.
		url: Full Airbnb listing URL (dates will be appended if missing).
		location: The search location (e.g. "Mexico City") passed to parsers.
		check_in: Check-in date (``YYYY-MM-DD``).
		check_out: Check-out date (``YYYY-MM-DD``).
		num_people: Number of people for cost breakdown.
		num_nights: Number of nights for the stay.
		search_listing: Optional search-card listing data to backfill
			fields that the listing detail page may not include.

	Returns:
		A ``ListingWithCost`` on success, or ``ListingFailure`` with
		the URL and error message on failure.
	"""
	context: Union[BrowserContext, None] = None
	try:
		context: BrowserContext = await browser.new_context(
			user_agent=(
				"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
				"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
			),
			viewport={"width": 1280, "height": 720},
		)
		page: Page = await context.new_page()

		# Ensure the URL has date params so Airbnb renders pricing
		full_url: str = _ensure_date_params(url, check_in, check_out, num_people)

		# ── Step 1: Listing page ──────────────────────────────────
		# Use "load" to wait for all sub-resources (scripts, styles) —
		# DOMContentLoaded fires too early for React hydration.
		#
		# networkidle is unreliable because Airbnb keeps persistent analytics/WebSocket connections open.
		await page.goto(full_url, wait_until="load", timeout=30000)
		info("Loaded listing page: {url}", url=full_url)

		# Wait for listing booking-widget signals before parsing and clicking.
		await _wait_for_listing_booking_widget_ready(page, full_url)

		# Capture listing page HTML for listing details extraction
		listing_html: str = await page.content()
		listing: AirbnbListing = parse_listing_details(
			location=location, page_html=listing_html
		)

		# ── Step 2: Booking page ──────────────────────────────────
		# Click the Reserve button to navigate to the checkout page
		# where parse_booking_price can find pd-value-TOTAL etc.
		reserve_selector: str = RESERVE_BUTTON_SELECTOR
		try:
			await page.wait_for_selector(reserve_selector, timeout=5000)
		except Exception:
			return ListingFailure(
				url=url,
				error=(
					"Reserve button not found — listing may be unavailable "
					"for the selected dates"
				),
			)

		# Use JavaScript click to bypass Airbnb's sticky header/footer
		# overlays that prevent Playwright's actionability checks from
		# scrolling the Reserve button into the visible viewport.
		# Standard page.click() fails with "element is outside of the
		# viewport" on ~40% of listings due to these fixed overlays.
		clicked: bool = await page.evaluate(
			f"""() => {{
				const btn = document.querySelector('{RESERVE_BUTTON_SELECTOR}');
				if (!btn) return false;
				btn.scrollIntoView({{block: 'center'}});
				btn.click();
				return true;
			}}"""
		)
		if not clicked:
			return ListingFailure(
				url=url,
				error="Reserve button found but could not be clicked",
			)
		info("Clicked Reserve for {url}", url=full_url)

		booking_ready: bool = await _wait_for_booking_page_ready(page, full_url)

		# Retry Reserve once when the click did not lead to booking signals.
		if not booking_ready:
			warning(
				"Booking signals absent after initial click for {url}; retrying Reserve once",
				url=full_url,
			)
			try:
				await page.locator(reserve_selector).first.click(
					force=True, timeout=5000
				)
				info("Retried Reserve click with force=True for {url}", url=full_url)
				await _wait_for_booking_page_ready(page, full_url)
			except Exception as retry_exc:
				warning(
					"Reserve retry click failed for {url}: {error}",
					url=full_url,
					error=f"{type(retry_exc).__name__}: {retry_exc}",
				)

		# Capture booking page HTML for price extraction
		booking_html: str = await page.content()
		cost: CostBreakdown = parse_booking_price(
			page_html=booking_html, num_people=num_people
		)

		# ── Backfill missing fields from search card ──────────────
		# The listing detail page may not include num_reviews,
		# num_bathrooms, or rating (e.g. JSON-LD doesn't always have
		# them).  Merge from the search-card data when available.
		# Also compute nightly_rate from cost breakdown if missing.
		merge_fields: dict[str, Any] = {}
		if search_listing is not None:
			if listing.num_reviews is None and search_listing.num_reviews is not None:
				merge_fields["num_reviews"] = search_listing.num_reviews
			if (
				listing.num_bathrooms is None
				and search_listing.num_bathrooms is not None
			):
				merge_fields["num_bathrooms"] = search_listing.num_bathrooms
			if listing.rating is None and search_listing.rating is not None:
				merge_fields["rating"] = search_listing.rating
			if listing.neighborhood is None and search_listing.neighborhood is not None:
				merge_fields["neighborhood"] = search_listing.neighborhood

		# Compute nightly_rate from cost breakdown if still unknown
		if listing.nightly_rate is None and "nightly_rate" not in merge_fields:
			if cost.num_nights > 0:
				merge_fields["nightly_rate"] = round(
					cost.total_cost / cost.num_nights, 2
				)

		if merge_fields:
			listing: AirbnbListing = listing.model_copy(update=merge_fields)

		return ListingWithCost(listing=listing, cost_breakdown=cost)
	except Exception as exc:
		# Individual listing failures should not crash the batch —
		# capture the error for structured reporting.
		error_msg: str = f"{type(exc).__name__}: {exc}"
		warning(
			"Failed to explore listing {url}: {error}. page_url={page_url}, page_title={page_title}",
			url=url,
			error=error_msg,
			page_url=page.url if "page" in locals() else "<unavailable>",
			page_title=(
				await _safe_page_title(page) if "page" in locals() else "<unavailable>"
			),
		)
		return ListingFailure(url=url, error=error_msg)
	finally:
		if context is not None:
			await context.close()


async def _explore_with_semaphore(
	semaphore: asyncio.Semaphore,
	browser: Browser,
	url: str,
	location: str,
	check_in: str,
	check_out: str,
	num_people: int,
	num_nights: int,
	index: int,
	search_listing: Union[AirbnbListing, None] = None,
) -> Union[ListingWithCost, ListingFailure]:
	"""Rate-limited wrapper around single-listing exploration.

	Uses a semaphore to limit concurrent browser contexts and adds a
	staggered delay to avoid burst-loading Airbnb pages.

	Args:
		semaphore: Concurrency limiter.
		browser: Shared Playwright browser instance.
		url: Full Airbnb listing URL.
		location: The search location (e.g. "Mexico City") passed to parsers.
		check_in: Check-in date (``YYYY-MM-DD``).
		check_out: Check-out date (``YYYY-MM-DD``).
		num_people: Number of people for cost breakdown.
		num_nights: Number of nights for the stay.
		index: Position in the batch (for stagger delay calculation).
		search_listing: Optional search-card listing data to backfill
			fields that the listing detail page may not include.

	Returns:
		A ``ListingWithCost`` on success, or ``ListingFailure`` on
		failure.
	"""
	async with semaphore:
		# Constant delay between requests to respect Airbnb rate limits
		if index > 0:
			await asyncio.sleep(_PAGE_LOAD_DELAY)
		return await _explore_single_listing(
			browser,
			url,
			location,
			check_in,
			check_out,
			num_people,
			num_nights,
			search_listing=search_listing,
		)


async def explore_listings(
	urls: list[str],
	location: str,
	check_in: str,
	check_out: str,
	num_people: int,
	num_nights: int,
	search_listings: Union[list[AirbnbListing], None] = None,
	constraints: Union[TripWeek, None] = None,
) -> Union[ExplorationResult, ExplorationWithAnalysis]:
	"""Explore multiple Airbnb listings in parallel.

	Launches a headless Chromium browser and opens each listing URL in
	an isolated browser context, up to ``MAX_CONCURRENT_BROWSERS``
	at a time.  Each listing's HTML is parsed for both listing details
	and booking price in a single page load (no separate availability
	check needed).

	The ``check_in`` and ``check_out`` dates are appended to each URL
	if not already present — without them Airbnb shows "Add dates
	for prices" and the price parser cannot extract a total.

	When ``search_listings`` is provided, fields that the listing
	detail page may not include (``num_reviews``, ``num_bathrooms``,
	``rating``, ``neighborhood``) are backfilled from the
	corresponding search-card data.  Matching is done by URL.

	When ``constraints`` is provided, the returned listings are
	automatically verified against the trip week constraints and
	ranked into categories — returning an ``ExplorationWithAnalysis``
	instead of a plain ``ExplorationResult``.

	Args:
		urls: List of full Airbnb listing URLs to explore.
		location: The search location (e.g. "Mexico City") passed to parsers.
		check_in: Check-in date (``YYYY-MM-DD``).
		check_out: Check-out date (``YYYY-MM-DD``).
		num_people: Number of people for cost breakdown.
		num_nights: Number of nights for the stay.
		search_listings: Optional list of search-card listings to
			backfill fields not found on detail pages.
		constraints: Optional trip week constraints.  When provided,
			succeeded listings are verified with ``verify_constraints``
			and ranked with ``rank_by_category``, returning an
			``ExplorationWithAnalysis``.

	Returns:
		An ``ExplorationResult`` (when no constraints) or
		``ExplorationWithAnalysis`` (when constraints provided).

	Raises:
		ValueError: If ``urls`` is empty or ``num_people`` < 1 or
			``num_nights`` < 1.
	"""
	if not urls:
		raise ValueError("urls must not be empty")
	if num_people < 1:
		raise ValueError("num_people must be at least 1")
	if num_nights < 1:
		raise ValueError("num_nights must be at least 1")

	# Build URL→search-listing lookup for backfilling
	search_lookup: dict[str, AirbnbListing] = {}
	if search_listings:
		for sl in search_listings:
			search_lookup[sl.url] = sl

	max_concurrent: int = settings.MAX_CONCURRENT_BROWSERS

	results: list[Union[ListingWithCost, ListingFailure]] = []

	async with async_playwright() as pw:
		browser: Browser = await pw.chromium.launch(headless=True)
		try:
			semaphore = asyncio.Semaphore(max_concurrent)
			tasks: list[
				CoroutineType[Any, Any, Union[ListingWithCost, ListingFailure]]
			] = [
				_explore_with_semaphore(
					semaphore,
					browser,
					url,
					location,
					check_in,
					check_out,
					num_people,
					num_nights,
					i,
					search_listing=search_lookup.get(url),
				)
				for i, url in enumerate(urls)
			]
			results: list[
				Union[ListingWithCost, ListingFailure]
			] = await asyncio.gather(*tasks)
		finally:
			await browser.close()

	# Partition into successes and failures
	succeeded: list[ListingWithCost] = []
	failed: list[ListingFailure] = []
	for result in results:
		if isinstance(result, ListingWithCost):
			succeeded.append(result)
		else:
			failed.append(result)

	info(
		"Exploration complete: {n_success}/{n_total} succeeded, {n_failed} failed",
		n_success=len(succeeded),
		n_total=len(urls),
		n_failed=len(failed),
	)

	# When constraints are provided, run verify + rank pipeline inline, returning an ExplorationWithAnalysis that includes constraint results, passed listings, and rankings by category.

	# This saves the agent from having to make additional calls to the verification and ranking tools.
	if constraints is not None:
		from src.airbnb.tools.analysis import rank_by_category, verify_constraints

		constraint_results: list[ConstraintResult] = verify_constraints(
			succeeded, constraints
		)
		passed_listings: list[ListingWithCost] = [
			cr.listing for cr in constraint_results if cr.passed
		]
		rankings: dict[str, Union[ListingWithCost, None]] = rank_by_category(
			passed_listings
		)

		return ExplorationWithAnalysis(
			succeeded=succeeded,
			failed=failed,
			constraint_results=constraint_results,
			passed_listings=passed_listings,
			rankings=rankings,
		)

	# If no constraints, return the plain ExplorationResult with successes and failures only.
	return ExplorationResult(succeeded=succeeded, failed=failed)
