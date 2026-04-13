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


async def _explore_single_listing(
	browser: Browser,
	url: str,
	location: str,
	num_people: int,
	num_nights: int,
) -> Union[ListingWithCost, None]:
	"""Explore a single listing in an isolated browser context.

	Opens the listing page, waits for content to load, extracts the
	full HTML, then parses listing details and booking price from it.

	Args:
		browser: Shared Playwright browser instance.
		url: Full Airbnb listing URL.
		location: The search location (e.g. "Mexico City") passed to parsers.
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

		await page.goto(url, wait_until="domcontentloaded", timeout=30000)
		# Wait for main content to render
		await page.wait_for_load_state("networkidle", timeout=15000)

		html: str = await page.content()

		# Parse listing details and booking price from the same HTML
		listing: AirbnbListing = parse_listing_details(
			location=location, page_html=html
		)
		cost: CostBreakdown = parse_booking_price(page_html=html, num_people=num_people)

		return ListingWithCost(listing=listing, cost_breakdown=cost)
	except Exception:
		# Individual listing failures should not crash the batch
		return None
	finally:
		if context is not None:
			await context.close()


async def _explore_with_semaphore(
	semaphore: asyncio.Semaphore,
	browser: Browser,
	url: str,
	location: str,
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
			browser, url, location, num_people, num_nights
		)


async def explore_listings(
	urls: list[str],
	location: str,
	num_people: int,
	num_nights: int,
) -> list[ListingWithCost]:
	"""Explore multiple Airbnb listings in parallel.

	Launches a headless Chromium browser and opens each listing URL in
	an isolated browser context, up to ``MAX_CONCURRENT_BROWSERS``
	at a time.  Each listing's HTML is parsed for both listing details
	and booking price in a single page load (no separate availability
	check needed).

	Args:
		urls: List of full Airbnb listing URLs to explore.
		location: The search location (e.g. "Mexico City") passed to parsers.
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
					semaphore, browser, url, location, num_people, num_nights, i
				)
				for i, url in enumerate(urls)
			]
			results: list[ListingWithCost | None] = await asyncio.gather(*tasks)
		finally:
			await browser.close()

	# Filter out failures
	return [r for r in results if r is not None]
