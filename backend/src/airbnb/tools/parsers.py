"""HTML parsers for Airbnb search results, listing details, and booking prices.

Uses BeautifulSoup with the ``lxml`` parser to extract structured listing
data from Airbnb pages.  Designed to work with both Playwright-rendered
live HTML (Playwright MCP via Agent Navigation) and cached HTML files in ``discovery/html/``.

Airbnb pages are heavily client-side rendered.  These parsers target
the embedded JSON data within ``<script>`` tags (structured data and
application bootstrap payloads) as the primary extraction strategy,
with DOM-based fallbacks where useful.
"""

import re
from re import Match, Pattern
from typing import Union

import orjson
from bs4 import BeautifulSoup, Tag
from bs4.element import AttributeValueList, NavigableString
from orjson import JSONDecodeError

from src.airbnb.schemas import AirbnbListing, CostBreakdown

# ── Constants ──

AIRBNB_ROOMS_PREFIX = "https://www.airbnb.com/rooms/"
ROOM_ID_PATTERN: Pattern[str] = re.compile(r"/rooms/(\d+)")
PRICE_PATTERN: Pattern[str] = re.compile(r"\$[\d,]+(?:\.\d{2})?")
RATING_PATTERN: Pattern[str] = re.compile(r"(\d+\.\d+)\s*(?:★|stars?)?", re.IGNORECASE)
REVIEW_COUNT_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*reviews?", re.IGNORECASE)
BEDS_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*bed(?:room)?s?", re.IGNORECASE)
BATHS_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*bath(?:room)?s?", re.IGNORECASE)
NIGHTLY_RATE_PATTERN: Pattern[str] = re.compile(
	r"\$(\d[\d,]*)\s*(?:per\s*)?night", re.IGNORECASE
)


def _parse_price(text: str) -> Union[float, None]:
	"""Extract a dollar amount from text.

	Args:
		text: Text potentially containing a price like ``$1,542.66``.

	Returns:
		The parsed float value, or ``None`` if no price is found.
	"""
	match: Union[Match[str], None] = PRICE_PATTERN.search(text)
	if match:
		return float(match.group().replace("$", "").replace(",", ""))
	return None


def _extract_json_ld(soup: BeautifulSoup) -> Union[dict, None]:
	"""Extract JSON-LD structured data from the page.

	Args:
		soup: Parsed BeautifulSoup document.

	Returns:
		The first JSON-LD object found, or ``None``.
	"""
	for script in soup.find_all("script", type="application/ld+json"):
		try:
			raw: str = str(script.string or "")
			data: Union[dict, list] = orjson.loads(raw)
			if isinstance(data, dict):
				return data
			if isinstance(data, list) and data:
				return data[0]
		except (JSONDecodeError, TypeError):
			continue
	return None


def _extract_bootstrap_data(soup: BeautifulSoup) -> Union[dict, None]:
	"""Extract Airbnb bootstrap data from embedded script tags.

	Airbnb embeds application data in ``<script id="data-deferred-state*">``
	or similar script tags containing JSON payloads.

	Args:
		soup: Parsed BeautifulSoup document.

	Returns:
		The parsed bootstrap data dict, or ``None``.
	"""
	for script in soup.find_all("script", id=re.compile(r"data-deferred-state")):
		try:
			raw = str(script.string or "")
			data: dict = orjson.loads(raw)
			if isinstance(data, dict):
				return data
		except (JSONDecodeError, TypeError):
			continue
	return None


def _find_listing_links(soup: BeautifulSoup) -> list[Tag]:
	"""Find all anchor tags linking to Airbnb listing pages.

	   For example, tries to find links like ``/rooms/12345678`` or full URLs like
	   ``https://www.airbnb.com/rooms/12345678`` in the ``search results`` page (per location and dates searched).

	Args:
		soup: Parsed BeautifulSoup document.

	Returns:
		List of ``<a>`` tags with ``href`` containing ``/rooms/``.

		example: [ <a href="/rooms/12345678" ...>, <a href="https://www.airbnb.com/rooms/12345678" ...>, ... ]
	"""
	return [
		a
		for a in soup.find_all("a", href=True)
		if isinstance(a["href"], str)
		and "/rooms/" in a["href"]
		and a["href"].startswith(("/rooms/", "https://"))
	]


def _extract_room_id(url: str) -> Union[str, None]:
	"""Extract the numeric room ID from an Airbnb URL.

	Args:
		url: An Airbnb listing URL.

	Returns:
		The room ID string, or ``None`` if not found.
	"""
	match: Union[Match[str], None] = ROOM_ID_PATTERN.search(url)
	return match.group(1) if match else None


def parse_search_results(page_html: str) -> list[AirbnbListing]:
	"""Extract partial listing data from an Airbnb search results page.

	Parses search result cards to extract title, price preview, rating,
	URL, and neighbourhood.  Uses embedded JSON data as the primary
	source and falls back to DOM-based extraction for listing links.

	Args:
		page_html: Full HTML content of an Airbnb search results page.

	Returns:
		A list of partially populated ``AirbnbListing`` objects.  Fields
		like ``num_bedrooms`` or ``total_cost`` may be ``None`` since
		they require visiting the individual listing page.
	"""
	soup = BeautifulSoup(page_html, "lxml")
	listings: list[AirbnbListing] = []
	seen_room_ids: set[str] = set()

	# Strategy 1: Extract from listing link cards in the DOM
	for link in _find_listing_links(soup):
		href: Union[str, AttributeValueList] = link["href"]
		if not isinstance(href, str):
			continue

		room_id: Union[str, None] = _extract_room_id(href)
		if not room_id or room_id in seen_room_ids:
			continue
		seen_room_ids.add(room_id)

		# Build the full URL
		if href.startswith("/"):
			url = f"https://www.airbnb.com{href}"
		else:
			url: str = href

		# Try to find a title from the nearest container
		title = ""
		container: Union[Tag, None] = (
			link.find_parent(["div", "article", "li"]) or link.find_parent()
		)
		if container:
			# Look for aria-label on the link or nearby elements
			if link.get("aria-label"):
				title = str(link["aria-label"])
			else:
				title_el: Union[Tag, None] = container.find(
					["h2", "h3", "span"],
					attrs={"data-testid": re.compile(r"title|listing-card")},
				)
				if title_el:
					title: str = title_el.get_text(strip=True)
				elif not title:
					# Fallback: use first meaningful text
					for text_el in container.find_all(
						["h2", "h3", "div", "span"], limit=5
					):
						text: str = text_el.get_text(strip=True)
						if text and len(text) > 5 and "$" not in text:
							title: str = text
							break

		if not title:
			title = f"Airbnb Listing {room_id}"

		# Extract price, rating, reviews from the container text
		container_text: str = container.get_text(" ", strip=True) if container else ""
		nightly_rate: Union[float, None] = None
		rating: Union[float, None] = None
		num_reviews: Union[int, None] = None
		neighborhood: Union[str, None] = None

		nightly_match: Union[Match[str], None] = NIGHTLY_RATE_PATTERN.search(
			container_text
		)
		if nightly_match:
			nightly_rate = float(nightly_match.group(1).replace(",", ""))

		rating_match: Union[Match[str], None] = RATING_PATTERN.search(container_text)
		if rating_match:
			parsed_rating = float(rating_match.group(1))
			if 0.0 <= parsed_rating <= 5.0:
				rating = parsed_rating

		review_match: Union[Match[str], None] = REVIEW_COUNT_PATTERN.search(
			container_text
		)
		if review_match:
			num_reviews = int(review_match.group(1))

		# Extract image URL
		image_url: Union[str, None] = None
		if container:
			img: Union[Tag, None] = container.find("img", src=True)
			if img:
				image_url = str(img["src"])

		listings.append(
			AirbnbListing(
				url=url,
				title=title,
				nightly_rate=nightly_rate,
				rating=rating,
				num_reviews=num_reviews,
				neighborhood=neighborhood,
				image_url=image_url,
			)
		)

	return listings


def parse_listing_details(page_html: str) -> AirbnbListing:
	"""Extract enriched listing data from an individual listing page.

	Parses the listing detail page to extract bedrooms, bathrooms,
	amenities, rating, reviews, and the full title.  Uses JSON-LD
	structured data when available and falls back to DOM patterns.

	Args:
		page_html: Full HTML content of an Airbnb listing detail page.

	Returns:
		An ``AirbnbListing`` with enriched detail fields.

	Raises:
		ValueError: If no listing URL can be determined from the page.
	"""
	soup = BeautifulSoup(page_html, "lxml")

	# Extract URL from canonical link or og:url meta
	url: str = ""
	canonical: Union[Tag, None] = soup.find("link", rel="canonical")
	if canonical and canonical.get("href"):
		url = str(canonical["href"])
	if not url:
		og_url: Union[Tag, None] = soup.find("meta", property="og:url")
		if og_url and og_url.get("content"):
			url = str(og_url["content"])
	if not url:
		# Try to find from the page's own URL in a saved-from comment
		for comment in soup.find_all(string=lambda t: t and "saved from url" in str(t)):
			match: Union[Match[str], None] = re.search(
				r"https://www\.airbnb\.com/rooms/\d+", str(comment)
			)
			if match:
				url: str = match.group()
				break

	# Extract title
	title: str = ""
	og_title: Union[Tag, None] = soup.find("meta", property="og:title")
	if og_title and og_title.get("content"):
		title = str(og_title["content"])
	if not title:
		h1: Union[Tag, None] = soup.find("h1")
		if h1:
			title: str = h1.get_text(strip=True)
	if not title:
		title_tag: Union[Tag, None] = soup.find("title")
		if title_tag:
			title: str = title_tag.get_text(strip=True)

	# Extract from JSON-LD
	json_ld: Union[dict, None] = _extract_json_ld(soup)
	rating: Union[float, None] = None
	num_reviews: Union[int, None] = None
	image_url: Union[str, None] = None

	if json_ld:
		aggregate_rating: Union[dict, None] = json_ld.get("aggregateRating", {})
		if aggregate_rating:
			rating: Union[float, None] = _safe_float(
				aggregate_rating.get("ratingValue")
			)
			num_reviews: Union[int, None] = _safe_int(
				aggregate_rating.get("reviewCount")
			)
		image_data: Union[str, list, None] = json_ld.get("image")
		if isinstance(image_data, str):
			image_url: str = image_data
		elif isinstance(image_data, list) and image_data:
			image_url = str(image_data[0])

	# Extract bedroom/bathroom counts from page text
	page_text: str = soup.get_text(" ", strip=True)
	num_bedrooms: Union[int, None] = None
	num_bathrooms: Union[int, None] = None
	num_beds: Union[int, None] = None

	beds_match: Union[Match[str], None] = BEDS_PATTERN.search(page_text)
	if beds_match:
		num_bedrooms = int(beds_match.group(1))
		num_beds: int = num_bedrooms  # default beds = bedrooms until refined

	baths_match: Union[Match[str], None] = BATHS_PATTERN.search(page_text)
	if baths_match:
		num_bathrooms = int(baths_match.group(1))

	# Extract amenities from the page
	amenities: Union[list[str], None] = _extract_amenities(soup)

	# Extract neighbourhood from meta description or page text
	neighborhood: Union[str, None] = None
	meta_desc: Union[Tag, None] = soup.find("meta", attrs={"name": "description"})
	if meta_desc and meta_desc.get("content"):
		desc = str(meta_desc["content"])
		# Look for neighbourhood-like patterns
		for pattern in [
			re.compile(r"in\s+([A-Z][a-zA-Z\s/]+(?:,\s*[A-Z][a-zA-Z\s]+)*)"),
		]:
			match: Union[Match[str], None] = pattern.search(desc)
			if match:
				neighborhood: str = match.group(1).strip()
				break

	# Fall back to DOM for rating/reviews if JSON-LD didn't provide them
	if rating is None:
		rating_match: Union[Match[str], None] = RATING_PATTERN.search(page_text)
		if rating_match:
			parsed_val = float(rating_match.group(1))
			if 0.0 <= parsed_val <= 5.0:
				rating: float = parsed_val

	if num_reviews is None:
		review_match: Union[Match[str], None] = REVIEW_COUNT_PATTERN.search(page_text)
		if review_match:
			num_reviews: int = int(review_match.group(1))

	# Extract nightly rate from page
	nightly_rate: Union[float, None] = None
	nightly_match: Union[Match[str], None] = NIGHTLY_RATE_PATTERN.search(page_text)
	if nightly_match:
		nightly_rate: float = float(nightly_match.group(1).replace(",", ""))

	if not url:
		raise ValueError("Could not determine listing URL from the page HTML")

	return AirbnbListing(
		url=url,
		title=title or "Untitled Listing",
		nightly_rate=nightly_rate,
		num_beds=num_beds,
		num_bedrooms=num_bedrooms,
		num_bathrooms=num_bathrooms,
		amenities=amenities,
		neighborhood=neighborhood,
		rating=rating,
		num_reviews=num_reviews,
		image_url=image_url,
	)


def parse_booking_price(page_html: str) -> CostBreakdown:
	"""Extract booking price breakdown from an Airbnb listing page.

	Parses the price breakdown shown after clicking Reserve, extracting
	total cost, nightly rate, and individual fees (cleaning, service,
	occupancy taxes, etc.).

	Args:
		page_html: Full HTML content of an Airbnb listing/booking page
			that includes the price breakdown section.

	Returns:
		A ``CostBreakdown`` with extracted cost data.  ``num_people``
		defaults to ``1`` and ``num_nights`` defaults to ``1`` — the
		caller should update these from the trip context.

	Raises:
		ValueError: If no total price can be extracted from the page.
	"""
	soup = BeautifulSoup(page_html, "lxml")
	page_text: str = soup.get_text(" ", strip=True)

	# Extract total cost — look for "Total" section
	total_cost: Union[float, None] = None
	fees: dict[str, float] = {}
	nightly_rate: Union[float, None] = None
	num_nights: int = 1

	# Look for price breakdown in structured elements
	# Airbnb typically shows: "$X × N nights", fees, then "Total"
	nights_pattern: Pattern[str] = re.compile(
		r"\$(\d[\d,]*(?:\.\d{2})?)\s*x\s*(\d+)\s*nights?", re.IGNORECASE
	)
	nights_match: Union[Match[str], None] = nights_pattern.search(page_text)
	if nights_match:
		nightly_rate: float = float(nights_match.group(1).replace(",", ""))
		num_nights: int = int(nights_match.group(2))

	# Extract fees from common patterns
	fee_patterns: dict[str, re.Pattern[str]] = {
		"cleaning_fee": re.compile(
			r"cleaning\s*fee\s*\$(\d[\d,]*(?:\.\d{2})?)", re.IGNORECASE
		),
		"service_fee": re.compile(
			r"(?:airbnb\s*)?service\s*fee\s*\$(\d[\d,]*(?:\.\d{2})?)", re.IGNORECASE
		),
		"occupancy_taxes": re.compile(
			r"(?:occupancy\s*)?taxes?\s*(?:and\s*fees?\s*)?\$(\d[\d,]*(?:\.\d{2})?)",
			re.IGNORECASE,
		),
	}

	for fee_name, pattern in fee_patterns.items():
		match: Union[Match[str], None] = pattern.search(page_text)
		if match:
			fees[fee_name] = float(match.group(1).replace(",", ""))

	# Extract total — look for "Total" followed by a price
	total_pattern: Pattern[str] = re.compile(
		r"total\s*(?:\(USD\)\s*)?\$(\d[\d,]*(?:\.\d{2})?)", re.IGNORECASE
	)
	total_match: Union[Match[str], None] = total_pattern.search(page_text)
	if total_match:
		total_cost = float(total_match.group(1).replace(",", ""))

	# Fallback: compute total from nightly rate + fees
	if total_cost is None and nightly_rate is not None:
		subtotal: float = nightly_rate * num_nights
		total_cost: float = subtotal + sum(fees.values())

	if total_cost is None:
		raise ValueError("Could not extract total price from the booking page HTML")

	# Default to 1 person / computed nights — caller updates via context
	return CostBreakdown(
		total_cost=total_cost,
		num_people=1,
		num_nights=num_nights,
		cost_per_person=round(total_cost, 2),
		cost_per_night=round(total_cost / max(num_nights, 1), 2),
		cost_per_night_per_person=round(total_cost / max(num_nights, 1), 2),
		fees=fees,
	)


def _extract_amenities(soup: BeautifulSoup) -> list[str]:
	"""Extract amenity names from the listing page.

	Args:
		soup: Parsed BeautifulSoup document.

	Returns:
		A deduplicated list of amenity names.
	"""
	amenities: list[str] = []
	seen: set[str] = set()

	# Look for amenities in common Airbnb DOM patterns
	# Pattern 1: data-testid attributes containing "amenity"
	for el in soup.find_all(attrs={"data-testid": re.compile(r"amenity")}):
		text: str = el.get_text(strip=True)
		if text and text.lower() not in seen:
			seen.add(text.lower())
			amenities.append(text)

	# Pattern 2: sections or divs with "amenity" or "What this place offers"
	amenity_section: Union[NavigableString, None] = soup.find(
		string=re.compile(r"What this place offers", re.IGNORECASE)
	)
	if amenity_section:
		parent: Union[Tag, None] = amenity_section.find_parent(["div", "section"])
		if parent:
			for item in parent.find_all(["li", "div", "span"]):
				text: str = item.get_text(strip=True)
				if (
					text
					and len(text) < 100
					and text.lower() not in seen
					and "show all" not in text.lower()
				):
					seen.add(text.lower())
					amenities.append(text)

	return amenities


def _safe_float(value: object) -> Union[float, None]:
	"""Safely convert a value to float.

	Args:
		value: Any value that might be numeric.

	Returns:
		The float value, or ``None`` if conversion fails.
	"""
	if value is None:
		return None
	try:
		return float(value)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
	except (ValueError, TypeError):
		return None


def _safe_int(value: object) -> Union[int, None]:
	"""Safely convert a value to int.

	Args:
		value: Any value that might be numeric.

	Returns:
		The int value, or ``None`` if conversion fails.
	"""
	if value is None:
		return None
	try:
		return int(value)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
	except (ValueError, TypeError):
		return None
