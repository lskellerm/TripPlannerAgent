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

from src.airbnb.schemas import (
	AirbnbListing,
	CostBreakdown,
	ExplorationResult,
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

	This two-page approach is necessary because
	``parse_booking_price`` expects the structured price elements
	(``pd-value-TOTAL``, ``pd-title-ACCOMMODATION``, etc.) that only
	appear on the booking/checkout page — *not* the listing page.

	The URL is enriched with ``check_in``/``check_out``/``adults``
	query parameters so that Airbnb renders pricing on the listing
	page.  Without dates the page shows "Add dates for prices" and
	the Reserve button may be absent.

	Args:
		browser: Shared Playwright browser instance.
		url: Full Airbnb listing URL (dates will be appended if missing).
		location: The search location (e.g. "Mexico City") passed to parsers.
		check_in: Check-in date (``YYYY-MM-DD``).
		check_out: Check-out date (``YYYY-MM-DD``).
		num_people: Number of people for cost breakdown.
		num_nights: Number of nights for the stay.

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
		# networkidle is unreliable because Airbnb keeps persistent
		# analytics/WebSocket connections open.
		await page.goto(full_url, wait_until="load", timeout=30000)
		info("Loaded listing page: {url}", url=full_url)

		# Wait for the booking sidebar to hydrate — it contains the
		# Reserve button we need to click next.
		try:
			await page.wait_for_selector(
				'[data-testid="book-it-default"]',
				timeout=8000,
			)
			info("Booking sidebar loaded for {url}", url=full_url)
		except Exception:
			# Booking sidebar selector not found — some page layouts
			# differ. Fall back to waiting for any price-like text
			# (e.g. "$X x N nights") which indicates React has rendered
			# the pricing widget.
			info(
				"Booking sidebar not found for {url}, waiting for price text instead",
			)
			try:
				await page.wait_for_selector(
					"text=/\\$[\\d,]+\\s*(x|×|for)\\s*\\d+\\s*night/i",
					timeout=5000,
				)
				info("Price text loaded for {url}", url=full_url)
			except Exception:
				warning(
					"Pricing selector wait timed out for {url}, "
					"proceeding with available content",
					url=full_url,
				)

		# Capture listing page HTML for listing details extraction
		listing_html: str = await page.content()
		listing: AirbnbListing = parse_listing_details(
			location=location, page_html=listing_html
		)

		# ── Step 2: Booking page ──────────────────────────────────
		# Click the Reserve button to navigate to the checkout page
		# where parse_booking_price can find pd-value-TOTAL etc.
		reserve_selector: str = '[data-testid="homes-pdp-cta-btn"]'
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

		await page.click(reserve_selector)
		info("Clicked Reserve for {url}", url=full_url)

		# Wait for the booking/checkout page to render its price
		# breakdown.  The primary indicator is pd-value-TOTAL; fall
		# back to the "Price details" heading text.
		try:
			await page.wait_for_selector(
				'[data-testid="pd-value-TOTAL"]',
				timeout=15000,
			)
			info("Booking page price loaded for {url}", url=full_url)
		except Exception:
			try:
				await page.wait_for_selector(
					"text=/Price details/i",
					timeout=5000,
				)
				info(
					"Booking page 'Price details' loaded for {url}",
					url=full_url,
				)
			except Exception:
				warning(
					"Booking page selectors timed out for {url}, "
					"proceeding with available content",
					url=full_url,
				)

		# Capture booking page HTML for price extraction
		booking_html: str = await page.content()
		cost: CostBreakdown = parse_booking_price(
			page_html=booking_html, num_people=num_people
		)

		return ListingWithCost(listing=listing, cost_breakdown=cost)
	except Exception as exc:
		# Individual listing failures should not crash the batch —
		# capture the error for structured reporting.
		error_msg: str = f"{type(exc).__name__}: {exc}"
		warning(
			"Failed to explore listing {url}: {error}",
			url=url,
			error=error_msg,
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

	Returns:
		A ``ListingWithCost`` on success, or ``ListingFailure`` on
		failure.
	"""
	async with semaphore:
		# Constant delay between requests to respect Airbnb rate limits
		if index > 0:
			await asyncio.sleep(_PAGE_LOAD_DELAY)
		return await _explore_single_listing(
			browser, url, location, check_in, check_out, num_people, num_nights
		)


async def explore_listings(
	urls: list[str],
	location: str,
	check_in: str,
	check_out: str,
	num_people: int,
	num_nights: int,
) -> ExplorationResult:
	"""Explore multiple Airbnb listings in parallel.

	Launches a headless Chromium browser and opens each listing URL in
	an isolated browser context, up to ``MAX_CONCURRENT_BROWSERS``
	at a time.  Each listing's HTML is parsed for both listing details
	and booking price in a single page load (no separate availability
	check needed).

	The ``check_in`` and ``check_out`` dates are appended to each URL
	if not already present — without them Airbnb shows "Add dates
	for prices" and the price parser cannot extract a total.

	Args:
		urls: List of full Airbnb listing URLs to explore.
		location: The search location (e.g. "Mexico City") passed to parsers.
		check_in: Check-in date (``YYYY-MM-DD``).
		check_out: Check-out date (``YYYY-MM-DD``).
		num_people: Number of people for cost breakdown.
		num_nights: Number of nights for the stay.

	Returns:
		An ``ExplorationResult`` containing ``succeeded`` (list of
		``ListingWithCost``) and ``failed`` (list of
		``ListingFailure`` with URL and error message for each
		listing that could not be parsed).

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

	return ExplorationResult(succeeded=succeeded, failed=failed)
