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

from logfire import warning
from playwright.async_api import (
	Browser,
	BrowserContext,
	Page,
	async_playwright,
)

from src.airbnb.schemas import AirbnbListing, CostBreakdown, ListingWithCost
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
) -> Union[ListingWithCost, None]:
	"""Explore a single listing in an isolated browser context.

	Opens the listing page, waits for content to load, extracts the
	full HTML, then parses listing details and booking price from it.

	The URL is enriched with ``check_in``/``check_out``/``adults``
	query parameters so that Airbnb renders pricing on the listing
	page.  Without dates the page shows "Add dates for prices" and
	no total cost can be extracted.

	Args:
		browser: Shared Playwright browser instance.
		url: Full Airbnb listing URL (dates will be appended if missing).
		location: The search location (e.g. "Mexico City") passed to parsers.
		check_in: Check-in date (``YYYY-MM-DD``).
		check_out: Check-out date (``YYYY-MM-DD``).
		num_people: Number of people for cost breakdown.
		num_nights: Number of nights for the stay.

	Returns:
		A ``ListingWithCost`` if parsing succeeds, or ``None`` on
		failure.
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

		await page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
		# Attempt networkidle but proceed on timeout — Airbnb pages often
		# have persistent connections (analytics, WebSockets) that prevent
		# networkidle from ever firing  The domcontent.loaded event is
		# sufficient for HTML data extraction since listing metadata lives
		# in embedded <script> tags (JSON-LD / bootstrap data).
		try:
			await page.wait_for_load_state("networkidle", timeout=15000)
		except Exception:
			# Log and ignore timeout errors from networkidle waits
			warning(
				"networkidle wait timed out for {url}, proceeding with DOMContentLoaded",
				url=full_url,
				_exc_info=True,
			)

		html: str = await page.content()

		# Parse listing details and booking price from the same HTML
		listing: AirbnbListing = parse_listing_details(
			location=location, page_html=html
		)
		cost: CostBreakdown = parse_booking_price(page_html=html, num_people=num_people)

		return ListingWithCost(listing=listing, cost_breakdown=cost)
	except Exception:
		# Individual listing failures should not crash the batch
		warning(
			"Failed to explore listing {url}",
			url=url,
			_exc_info=True,
		)
		return None
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
) -> Union[ListingWithCost, None]:
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
		A ``ListingWithCost`` if parsing succeeds, or ``None``.
	"""
	async with semaphore:
		# Stagger requests to avoid burst-loading
		if index > 0:
			await asyncio.sleep(_PAGE_LOAD_DELAY * index)
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
) -> list[ListingWithCost]:
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
		A list of successfully parsed ``ListingWithCost`` objects.
		Failed listings are silently skipped.

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

	results: list[Union[ListingWithCost, None]] = []

	async with async_playwright() as pw:
		browser: Browser = await pw.chromium.launch(headless=True)
		try:
			semaphore = asyncio.Semaphore(max_concurrent)
			tasks: list[CoroutineType[Any, Any, ListingWithCost | None]] = [
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
			results: list[ListingWithCost | None] = await asyncio.gather(*tasks)
		finally:
			await browser.close()

	# Filter out failures
	return [r for r in results if r is not None]
