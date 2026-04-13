"""HTML parsers for Airbnb search results, listing details, and booking prices.

Uses BeautifulSoup with the ``lxml`` parser to extract structured listing
data from Airbnb pages.  Designed to work with both Playwright-rendered
live HTML (saved to disk via ``browser_evaluate`` and the file-based bridge)
and cached HTML files in ``discovery/html/``.

Each public parser accepts two mutually exclusive input modes:

- ``html_file`` — filename (relative to ``PLAYWRIGHT_OUTPUT_DIR``) or absolute
  path.  The parser reads the file from disk, keeping large HTML payloads
  out of the LLM's context window.
- ``page_html`` — raw HTML string, for unit tests and cached-mode usage.

Airbnb pages are heavily client-side rendered.  These parsers target
the embedded JSON data within ``<script>`` tags (structured data and
application bootstrap payloads) as the primary extraction strategy,
with DOM-based fallbacks where useful.
"""

import re
from pathlib import Path
from re import Match, Pattern
from typing import Union
from urllib.parse import urlparse

import orjson
from bs4 import BeautifulSoup, Tag
from bs4.element import AttributeValueList
from orjson import JSONDecodeError
from pydantic_ai.exceptions import ModelRetry

from src.airbnb.constants import (
	BATHS_PATTERN,
	BEDROOMS_PATTERN,
	BEDS_ONLY_PATTERN,
	CITY_SUFFIXES,
	DISCOUNTED_PRICE_PATTERN,
	FOR_N_NIGHTS_PATTERN,
	H1_TITLE_LOCATION_PATTERN,
	KNOWN_CDMX_NEIGHBORHOOD_ABBREVIATIONS,
	MAX_CARD_TEXT_LENGTH,
	MAX_NEIGHBORHOOD_LENGTH,
	MIN_NEIGHBORHOOD_LENGTH,
	NEIGHBORHOOD_TESTID_PATTERN,
	NIGHTLY_RATE_PATTERN,
	OG_TITLE_LOCATION_PATTERN,
	OG_TITLE_ROOM_PATTERN,
	PRICE_PATTERN,
	RATE_OPTION_TOTAL_PATTERN,
	RATING_PATTERN,
	REVIEW_COUNT_PATTERN,
	ROOM_ID_PATTERN,
	TOTAL_PRICE_PATTERN,
)
from src.airbnb.schemas import AirbnbListing, CostBreakdown, ListingWithCost
from src.core.config import settings


def _unwrap_json_string(content: str) -> str:
	"""Unwrap HTML content that was JSON-stringified by ``browser_evaluate``.

	Playwright MCP's ``browser_evaluate`` serialises the return value of
	the evaluated JavaScript expression as a JSON string before writing
	it to disk.

	When the expression is
	``() => document.documentElement.outerHTML``, the result is the full
	HTML wrapped in double quotes with all internal quotes escaped
	(``\\\"``).


	This helper detects the wrapping and decodes it.

	Args:
		content: Raw file content that may or may not be JSON-wrapped.

	Returns:
		The unwrapped HTML string if JSON-wrapped, or the original
		content unchanged.
	"""
	if content.startswith('"') and content.endswith('"'):
		try:
			decoded: Union[str, object] = orjson.loads(content)
			if isinstance(decoded, str):
				return decoded
		except (JSONDecodeError, TypeError):
			pass
	return content


def _resolve_html(
	html_file: Union[str, None] = None,
	page_html: Union[str, None] = None,
) -> str:
	"""Resolve HTML content from a file path or a raw string.

	Exactly one of ``html_file`` or ``page_html`` must be provided.

	When ``html_file`` is given:
	- If it is an absolute path, read that file directly.
	- Otherwise, treat it as relative to ``settings.PLAYWRIGHT_OUTPUT_DIR``.

	Files produced by Playwright MCP's ``browser_evaluate`` are
	JSON-stringified (wrapped in ``"..."`` with escaped internal
	quotes).  This function transparently unwraps them.

	Args:
		html_file: Filename (relative to output dir) or absolute path to
			an HTML file saved by ``browser_evaluate``.
		page_html: Raw HTML string (used in tests or cached mode).

	Returns:
		The HTML content as a string.

	Raises:
		ValueError: If neither or both arguments are provided.
		ModelRetry: If ``html_file`` points to a non-existent path.
			Raised as ``ModelRetry`` instead of ``FileNotFoundError`` so
			the agent receives the error as feedback and can retry with
			the correct filename.
	"""
	if (html_file is None) == (page_html is None):
		raise ValueError(
			"Exactly one of 'html_file' or 'page_html' must be provided, not both or neither."
		)

	if page_html is not None:
		return page_html

	# html_file is guaranteed non-None after the mutual-exclusivity check above.
	assert html_file is not None
	path = Path(html_file)
	if path.is_absolute():
		if not path.is_file():
			raise ModelRetry(
				f"HTML file not found: {path}. "
				f"Use the exact filename you passed to browser_evaluate's "
				f"'filename' parameter (e.g. 'listing_<room_id>.html')."
			)
		return _unwrap_json_string(path.read_text(encoding="utf-8"))

	# Relative path: check PLAYWRIGHT_OUTPUT_DIR first, then CWD.
	# Playwright MCP's ``browser_evaluate`` saves result files to the
	# process working directory (CWD), NOT to ``--output-dir``.  Snapshots
	# and screenshots go to ``--output-dir``.  We check both locations so
	# parsers work regardless of which tool produced the file.
	candidates: list[Path] = [
		Path(settings.PLAYWRIGHT_OUTPUT_DIR) / path,
		Path.cwd() / path,
	]
	for candidate in candidates:
		if candidate.is_file():
			return _unwrap_json_string(candidate.read_text(encoding="utf-8"))

	searched: str = ", ".join(str(c) for c in candidates)
	raise ModelRetry(
		f"HTML file not found: {html_file} (searched: {searched}). "
		f"Use the exact filename you passed to browser_evaluate's "
		f"'filename' parameter (e.g. 'listing_<room_id>.html'). "
		f"Do NOT use filenames from snapshot paths or console log entries."
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


# ── Neighbourhood Normalisation ──

# Pre-built case-insensitive lookup: lowercase key → canonical name.
_CDMX_LOWER_MAP: dict[str, str] = {
	k.lower(): v for k, v in KNOWN_CDMX_NEIGHBORHOOD_ABBREVIATIONS.items()
}

# Pre-compiled word-boundary patterns for known neighbourhood names,
# sorted longest-first so the most specific match wins.
_CDMX_SCAN_PATTERNS: list[tuple[Pattern[str], str]] = sorted(
	[
		(re.compile(rf"\b{re.escape(key)}\b", re.IGNORECASE), canonical)
		for key, canonical in KNOWN_CDMX_NEIGHBORHOOD_ABBREVIATIONS.items()
	],
	key=lambda t: len(t[0].pattern),
	reverse=True,
)


def _normalize_neighborhood(candidate: str, location: str) -> str:
	"""Normalise an extracted neighbourhood name via the CDMX mapping.

	Performs a case-insensitive exact lookup first.  If that fails, strips
	common city-name suffixes (e.g. ", CDMX", " of Mexico City") and tries
	again.

	Args:
		candidate: Raw neighbourhood string extracted from the page.
		location: The search location (e.g. "Mexico City") to help determine what normalization rules to apply.

	Returns:
		The canonical neighbourhood name if found in the mapping,
		otherwise the original ``candidate`` unchanged.
	"""
	lowered: str = candidate.strip().lower()

	if location.lower() == "mexico city":
		if lowered in _CDMX_LOWER_MAP:
			return _CDMX_LOWER_MAP[lowered]

		# Try stripping common city-name suffixes.
		for suffix in CITY_SUFFIXES:
			if lowered.endswith(suffix.lower()):
				trimmed: str = lowered[: -len(suffix)].strip()
				if trimmed in _CDMX_LOWER_MAP:
					return _CDMX_LOWER_MAP[trimmed]

	return candidate


def _scan_for_known_neighborhoods(text: str, location: str) -> Union[str, None]:
	"""Scan free text for any known CDMX neighbourhood name.

	Uses pre-compiled word-boundary regex patterns, checked longest-first
	so that ``"Historic Center"`` is matched before ``"Centro"``.

	Args:
		text: Arbitrary text to scan (e.g. an H1 title or listing name).
		location: The search location (e.g. "Mexico City") to help determine what regex patter is used (country/location specific patterns can be added in the future if needed).
	Returns:
		The canonical neighbourhood name if a match is found, or ``None``.
	"""
	if location.lower() == "mexico city":
		for pattern, canonical in _CDMX_SCAN_PATTERNS:
			if pattern.search(text):
				return canonical
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


def _find_similar_dates_links(soup: BeautifulSoup) -> set[int]:
	"""Identify listing links inside the 'Available for similar dates' section.

	Airbnb search pages sometimes append a carousel of listings
	available on *different* dates.  These listings will fail at
	the booking step (e.g. "This place is no longer available")
	because their URLs carry non-matching check-in/check-out dates.

	This function finds the carousel container by locating the
	heading element (``<h2>`` or ``<h3>``) whose text contains
	"similar dates", then walks up to the nearest ``role="group"``
	ancestor (the carousel wrapper) and collects the ``id()`` of
	every listing ``<a>`` tag inside it.

	Args:
		soup: Parsed BeautifulSoup document of a search results page.

	Returns:
		A set of Python ``id()`` values for ``<a>`` tags that should
		be excluded from results.  Empty set if no such section exists.
	"""
	similar_heading: Union[Tag, None] = soup.find(
		lambda tag: (
			tag.name in ("h2", "h3")
			and "similar dates" in tag.get_text(strip=True).lower()
		)
	)
	if similar_heading is None:
		return set()

	similar_container: Union[Tag, None] = similar_heading.find_parent(
		attrs={"role": "group"}
	) or similar_heading.find_parent("section")
	if similar_container is None:
		return set()

	return {
		id(a)
		for a in similar_container.find_all("a", href=True)
		if isinstance(a["href"], str) and "/rooms/" in a["href"]
	}


def parse_search_results(
	location: str,
	html_file: Union[str, None] = None,
	page_html: Union[str, None] = None,
) -> list[AirbnbListing]:
	"""Extract partial listing data from an Airbnb search results page.

		Parses search result cards to extract title, price preview, rating,
		URL, and neighbourhood.  Uses embedded JSON data as the primary
		source and falls back to DOM-based extraction for listing links.
	parse_search
		Accepts either a file path (for the file-based HTML bridge with
		Playwright MCP) or a raw HTML string (for tests / cached mode).

		Args:
			location: The search location (e.g. "Mexico City") to help determine what normalization rules to apply when extracting neighbourhood names.
			html_file: Filename relative to ``PLAYWRIGHT_OUTPUT_DIR`` or an
				absolute path to a saved HTML file.
			page_html: Raw HTML string of an Airbnb search results page.

		Returns:
			A list of partially populated ``AirbnbListing`` objects.  Fields
			like ``num_bedrooms`` or ``total_cost`` may be ``None`` since
			they require visiting the individual listing page.
	"""
	html_content: str = _resolve_html(html_file=html_file, page_html=page_html)
	soup = BeautifulSoup(html_content, "lxml")
	listings: list[AirbnbListing] = []
	seen_room_ids: set[str] = set()

	# Detect the "Available for similar dates" carousel section.
	# Airbnb search pages sometimes include listings with different
	# check-in/check-out dates in a separate carousel at the bottom.
	# These must be excluded — they don't match the user's requested
	# dates and will fail at the booking step.
	similar_dates_links: set[int] = _find_similar_dates_links(soup)

	# Strategy 1: Extract from listing link cards in the DOM
	for link in _find_listing_links(soup):
		# Skip listings from the "Available for similar dates" section.
		if id(link) in similar_dates_links:
			continue
		href: Union[str, AttributeValueList] = link["href"]
		if not isinstance(href, str):
			continue

		room_id: Union[str, None] = _extract_room_id(href)
		if not room_id or room_id in seen_room_ids:
			continue
		seen_room_ids.add(room_id)

		# Build a clean URL — strip tracking query params that inflate
		# token counts when the full listing list is serialised for the
		# LLM.  Keep only the /rooms/<room_id> path.
		if href.startswith("/"):
			clean_path: str = urlparse(href).path
			url = f"https://www.airbnb.com{clean_path}"
		else:
			clean_path: str = urlparse(href).path
			url: str = f"https://www.airbnb.com{clean_path}"

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
		total_cost: Union[float, None] = None
		nightly_rate: Union[float, None] = None
		rating: Union[float, None] = None
		num_reviews: Union[int, None] = None
		neighborhood: Union[str, None] = None

		# Strategy 1: look for "$X per night" or "$X night" (explicit nightly rate)
		nightly_match: Union[Match[str], None] = NIGHTLY_RATE_PATTERN.search(
			container_text
		)
		if nightly_match:
			nightly_rate = float(nightly_match.group(1).replace(",", ""))

		# Strategy 2: Airbnb search cards often show the total stay price
		# as "$X Show price breakdown for N nights" or "$X for N nights".
		# Extract total_cost and compute nightly_rate from it.
		if nightly_rate is None:
			total_match: Union[Match[str], None] = TOTAL_PRICE_PATTERN.search(
				container_text
			)
			if total_match:
				total_cost = float(total_match.group(1).replace(",", ""))
				nights: int = int(total_match.group(2))
				if nights > 0:
					nightly_rate: float = round(total_cost / nights, 2)

		# Strategy 3: just grab the first dollar amount as a price hint
		if nightly_rate is None and total_cost is None:
			price_match: Union[Match[str], None] = PRICE_PATTERN.search(container_text)
			if price_match:
				total_cost = float(
					price_match.group().replace("$", "").replace(",", "")
				)

		rating_match: Union[Match[str], None] = RATING_PATTERN.search(container_text)
		if rating_match:
			parsed_rating: float = float(rating_match.group(1))
			if 0.0 <= parsed_rating <= 5.0:
				rating: float = parsed_rating

		review_match: Union[Match[str], None] = REVIEW_COUNT_PATTERN.search(
			container_text
		)
		if review_match:
			num_reviews: int = int(review_match.group(1))

		# Extract neighborhood from the listing card.
		# Airbnb cards often show "Neighbourhood · Property type · beds · baths"
		# in a subtitle element or similar inline text.
		if container:
			# Strategy 1: look for an element with a data-testid hinting at subtitle/location
			subtitle_el: Union[Tag, None] = container.find(
				["div", "span"],
				attrs={"data-testid": NEIGHBORHOOD_TESTID_PATTERN},
			)
			if subtitle_el:
				subtitle_text: str = subtitle_el.get_text(strip=True)
				if "·" in subtitle_text and "$" not in subtitle_text:
					nb_candidate: str = subtitle_text.split("·", 1)[0].strip()
					if (
						MIN_NEIGHBORHOOD_LENGTH
						<= len(nb_candidate)
						<= MAX_NEIGHBORHOOD_LENGTH
					):
						neighborhood = nb_candidate

			# Strategy 2: scan card children for middle-dot separator text.
			# Validate candidates against the known-neighbourhood list to
			# avoid accepting listing-title fragments (e.g. "Bright Apt").
			if neighborhood is None:
				for child in container.find_all(["div", "span", "p"]):
					child_text: str = child.get_text(strip=True)
					if (
						"·" in child_text
						and "$" not in child_text
						and len(child_text) < MAX_CARD_TEXT_LENGTH
					):
						nb_candidate: str = child_text.split("·", 1)[0].strip()
						if (
							MIN_NEIGHBORHOOD_LENGTH
							<= len(nb_candidate)
							<= MAX_NEIGHBORHOOD_LENGTH
							and not nb_candidate[0].isdigit()
						):
							# Only accept if the candidate matches a known
							# neighbourhood — raw dot-split text is often
							# a listing title fragment, not a location.
							validated: Union[str, None] = _scan_for_known_neighborhoods(
								nb_candidate, location
							)
							if validated is not None:
								neighborhood = validated
								break

		# Extract image URL
		image_url: Union[str, None] = None
		if container:
			img: Union[Tag, None] = container.find("img", src=True)
			if img:
				image_url = str(img["src"])

		# Extract beds/bedrooms from listing-card-subtitle elements.
		# Airbnb search cards present room details in a subtitle element
		# whose text reads e.g. "2 bedrooms 2 bedrooms 2 beds , · 2 beds".
		# NOTE: The listing *name* subtitle can also contain "bed" (e.g.
		# "Brand New 2-Bedroom ...") but won't match the regex patterns.
		# Only break when at least one regex actually matched.
		num_bedrooms: Union[int, None] = None
		num_beds: Union[int, None] = None
		if container:
			for subtitle in container.find_all(
				attrs={"data-testid": "listing-card-subtitle"}
			):
				sub_text: str = subtitle.get_text(" ", strip=True)
				if not sub_text:
					continue
				# Only consider subtitles that mention bed/bedroom
				if "bed" not in sub_text.lower():
					continue
				br_match: Union[Match[str], None] = BEDROOMS_PATTERN.search(sub_text)
				if br_match:
					num_bedrooms = int(br_match.group(1))
				bd_match: Union[Match[str], None] = BEDS_ONLY_PATTERN.search(sub_text)
				if bd_match:
					num_beds = int(bd_match.group(1))
				if br_match or bd_match:
					break  # only stop after a successful regex match

		# Strategy 3: Keyword scan of the host-given title for known
		# neighbourhood names (e.g. "Heart Condesa" → "Condesa").
		# This runs BEFORE the listing-card-title fallback because the
		# host title often embeds the real neighbourhood, while the card
		# title typically only gives city-level info ("Mexico City").
		if neighborhood is None and title:
			neighborhood = _scan_for_known_neighborhoods(title, location)

		# Strategy 4 (fallback): Extract location from listing-card-title.
		# Airbnb cards have a data-testid="listing-card-title" element with
		# text like "Apartment in Mexico City" which provides the property
		# type and city.  Only used when prior strategies found nothing.
		if neighborhood is None and container:
			title_el: Union[Tag, None] = container.find(
				attrs={"data-testid": "listing-card-title"}
			)
			if title_el:
				title_text: str = title_el.get_text(strip=True)
				# Extract location after "in " prefix (e.g. "Apartment in Mexico City")
				in_match: Union[Match[str], None] = re.search(
					r"\bin\s+(.+)", title_text
				)
				if in_match:
					loc_candidate: str = in_match.group(1).strip()
					if (
						MIN_NEIGHBORHOOD_LENGTH
						<= len(loc_candidate)
						<= MAX_NEIGHBORHOOD_LENGTH
					):
						neighborhood = loc_candidate

		# Normalise the final neighbourhood through known locations abbreviations mapping
		if neighborhood is not None:
			neighborhood = _normalize_neighborhood(neighborhood, location)

		listings.append(
			AirbnbListing(
				url=url,
				title=title,
				total_cost=total_cost,
				nightly_rate=nightly_rate,
				num_beds=num_beds,
				num_bedrooms=num_bedrooms,
				rating=rating,
				num_reviews=num_reviews,
				neighborhood=neighborhood,
				image_url=image_url,
			)
		)

	return listings


def parse_listing_details(
	location: str,
	html_file: Union[str, None] = None,
	page_html: Union[str, None] = None,
) -> AirbnbListing:
	"""Extract enriched listing data from an individual listing page.

	Parses the listing detail page to extract bedrooms, bathrooms,
	amenities, rating, reviews, and the full title.  Uses JSON-LD
	structured data when available and falls back to DOM patterns.

	Accepts either a file path (for the file-based HTML bridge with
	Playwright MCP) or a raw HTML string (for tests / cached mode).

	Args:
	location: The search location (e.g. "Mexico City") to help determine what normalization rules to apply when extracting neighbourhood names.
		html_file: Filename relative to ``PLAYWRIGHT_OUTPUT_DIR`` or an
			absolute path to a saved HTML file.
		page_html: Raw HTML string of an Airbnb listing detail page.

	Returns:
		An ``AirbnbListing`` with enriched detail fields.

	Raises:
		ValueError: If no listing URL can be determined from the page.
	"""
	html_content: str = _resolve_html(html_file=html_file, page_html=page_html)
	soup = BeautifulSoup(html_content, "lxml")

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
	h1_text: str = ""
	og_title: Union[Tag, None] = soup.find("meta", property="og:title")
	if og_title and og_title.get("content"):
		title = str(og_title["content"])
	h1: Union[Tag, None] = soup.find("h1")
	if h1:
		h1_text = h1.get_text(strip=True)
	if not title:
		if h1_text:
			title = h1_text
		else:
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

	# Extract bedroom/bathroom counts from og:title first (most reliable).
	# Airbnb og:title format:
	#   "Home in Mexico City · ★4.88 · 1 bedroom · 1 bed · 1 private bath"
	num_bedrooms: Union[int, None] = None
	num_bathrooms: Union[float, None] = None
	num_beds: Union[int, None] = None

	if title:
		for og_match in OG_TITLE_ROOM_PATTERN.finditer(title):
			if og_match.group(1) and num_bedrooms is None:
				num_bedrooms = int(og_match.group(1))
			elif og_match.group(2) and num_beds is None:
				num_beds = int(og_match.group(2))
			elif og_match.group(3) and num_bathrooms is None:
				num_bathrooms = float(og_match.group(3))

	# Fall back to page text extraction if og:title didn't provide counts
	page_text: str = soup.get_text(" ", strip=True)

	if num_bedrooms is None:
		bedrooms_match: Union[Match[str], None] = BEDROOMS_PATTERN.search(page_text)
		if bedrooms_match:
			num_bedrooms = int(bedrooms_match.group(1))

	if num_beds is None:
		beds_match: Union[Match[str], None] = BEDS_ONLY_PATTERN.search(page_text)
		if beds_match:
			num_beds = int(beds_match.group(1))

	if num_bathrooms is None:
		baths_match: Union[Match[str], None] = BATHS_PATTERN.search(page_text)
		if baths_match:
			num_bathrooms = float(baths_match.group(1))

	# Extract amenities from the page via bootstrap JSON data
	amenities: Union[list[str], None] = _extract_amenities(soup)

	# Extract neighbourhood.
	# Strategy priority:
	#   1. Known-neighbourhood keyword scan on H1 text — catches names
	#      embedded anywhere in the host-given title regardless of grammar
	#   2. H1 regex pattern — structural "in/at/near {Location}" extraction
	#   3. og:title — reliable but usually only city-level
	#      (e.g. "Rental unit in Mexico City · ★5.0 · ...")
	#   4. meta description — same pattern as H1 text on Airbnb 	pages
	# All results are normalised through the CDMX abbreviation mapping.
	neighborhood: Union[str, None] = None

	# Strategy 1: Keyword scan H1 for known neighbourhoods
	if h1_text:
		neighborhood = _scan_for_known_neighborhoods(h1_text, location)

	# Strategy 2: H1 regex — structural "in/at/near {Location}" extraction
	if neighborhood is None and h1_text:
		h1_loc_match: Union[Match[str], None] = H1_TITLE_LOCATION_PATTERN.search(
			h1_text
		)
		if h1_loc_match:
			candidate: str = h1_loc_match.group(1).strip()
			if MIN_NEIGHBORHOOD_LENGTH <= len(candidate) <= MAX_NEIGHBORHOOD_LENGTH:
				neighborhood = _normalize_neighborhood(candidate, location)

	# Strategy 3: og:title for city-level fallback
	if neighborhood is None and title:
		loc_match: Union[Match[str], None] = OG_TITLE_LOCATION_PATTERN.search(title)
		if loc_match:
			candidate = loc_match.group(1).strip()
			if MIN_NEIGHBORHOOD_LENGTH <= len(candidate) <= MAX_NEIGHBORHOOD_LENGTH:
				neighborhood = _normalize_neighborhood(candidate, location)

	# Strategy 4: meta description
	if neighborhood is None:
		meta_desc: Union[Tag, None] = soup.find("meta", attrs={"name": "description"})
		if meta_desc and meta_desc.get("content"):
			desc = str(meta_desc["content"])
			for pattern in [
				re.compile(r"in\s+([A-Z][a-zA-Z\s/]+(?:,\s*[A-Z][a-zA-Z\s]+)*)"),
			]:
				match: Union[Match[str], None] = pattern.search(desc)
				if match:
					neighborhood = _normalize_neighborhood(
						match.group(1).strip(), location
					)
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
	# TODO: This is currently not working, and so parse_listing_details will return None for nightly_rate.
	# We need to find a new strategy to reliably extract the nightly rate from the listing page.
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


def parse_booking_price(
	html_file: Union[str, None] = None,
	page_html: Union[str, None] = None,
	num_people: int = 1,
) -> CostBreakdown:
	"""Extract booking price breakdown from an Airbnb booking/checkout page.

	Parses the price breakdown from the booking page ("Request to book")
	that appears after clicking Reserve on a listing page.  Extracts
	total cost, nightly rate, and individual fees (cleaning, service,
	occupancy taxes, etc.).

	The primary extraction strategy uses the ``data-testid="pd-value-TOTAL"``
	attribute on the checkout page's total price element.  Falls back to
	regex-based text extraction for listing pages or alternative HTML
	structures.

	Accepts either a file path (for the file-based HTML bridge with
	Playwright MCP) or a raw HTML string (for tests / cached mode).

	Args:
		html_file: Filename relative to ``PLAYWRIGHT_OUTPUT_DIR`` or an
			absolute path to a saved HTML file.
		page_html: Raw HTML string of an Airbnb booking/checkout page
			or listing page that includes pricing information.
		num_people: Number of people splitting the cost.  The HTML does
			not contain this information so the caller (agent) must
			provide it based on the user's trip request.  Defaults to
			``1`` for backward compatibility.

	Returns:
		A ``CostBreakdown`` with extracted cost data. ``num_nights`` is
		parsed from the page when available and otherwise defaults to ``1``.

	Raises:
		ModelRetry: If no total price can be extracted from the page.
		ValueError: If ``num_people`` is less than ``1``.
	"""
	if num_people < 1:
		raise ValueError("num_people must be at least 1.")

	html_content: str = _resolve_html(html_file=html_file, page_html=page_html)

	# Detect the LISTING_UNAVAILABLE sentinel from the agent's browser_evaluate
	# availability check.  When saved to a file via Playwright MCP, the
	# JSON-stringified value is decoded by _resolve_html / _unwrap_json_string.
	_stripped_content: str = html_content.strip()
	if _stripped_content in ("LISTING_UNAVAILABLE", '"LISTING_UNAVAILABLE"'):
		raise ModelRetry(
			"Listing is unavailable for the selected dates — the booking "
			"page returned LISTING_UNAVAILABLE.  Skip this listing and "
			"move to the next one.  Do NOT retry or call parse_booking_price "
			"for this listing again."
		)

	soup = BeautifulSoup(html_content, "lxml")
	page_text: str = soup.get_text(" ", strip=True)

	# ── Primary: structured data-testid extraction (booking page) ──
	# The Airbnb checkout/booking page uses `data-testid="pd-value-TOTAL"`
	# on the total price element.  This is the most reliable extraction
	# method when the HTML comes from the booking page.
	total_from_testid: Union[float, None] = None
	total_el: Union[Tag, None] = soup.find(  # type: ignore[assignment]
		attrs={"data-testid": "pd-value-TOTAL"}
	)
	if total_el is not None:
		_testid_price_match: Union[Match[str], None] = PRICE_PATTERN.search(
			total_el.get_text()
		)
		if _testid_price_match:
			total_from_testid = float(
				_testid_price_match.group(0).replace("$", "").replace(",", "")
			)

	# Extract total cost — look for "Total" section
	total_cost: Union[float, None] = total_from_testid
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
		nightly_rate = float(nights_match.group(1).replace(",", ""))
		num_nights = int(nights_match.group(2))

	# Booking page format: "N nights x $rate" (reversed order)
	if nightly_rate is None:
		booking_nights_pattern: Pattern[str] = re.compile(
			r"(\d+)\s*nights?\s*x\s*\$(\d[\d,]*(?:\.\d{2})?)", re.IGNORECASE
		)
		booking_nights_match: Union[Match[str], None] = booking_nights_pattern.search(
			page_text
		)
		if booking_nights_match:
			num_nights = int(booking_nights_match.group(1))
			nightly_rate = float(booking_nights_match.group(2).replace(",", ""))

	# Fallback: look for "$X for N nights" format (listing page without
	# expanded price breakdown — the default view before clicking Reserve).
	if nightly_rate is None:
		for_nights_match: Union[Match[str], None] = FOR_N_NIGHTS_PATTERN.search(
			page_text
		)
		if for_nights_match:
			total_cost = float(for_nights_match.group(1).replace(",", ""))
			num_nights = int(for_nights_match.group(2))
			if num_nights > 0:
				nightly_rate = round(total_cost / num_nights, 2)

	# Try the "$X $Y Show price breakdown for N nights" format where $X is
	# the strikethrough (original) price and $Y is the discounted price.
	# This must be checked before TOTAL_PRICE_PATTERN which would capture
	# the wrong (original) price from the same text.
	if total_cost is None and nightly_rate is None:
		discounted_match: Union[Match[str], None] = DISCOUNTED_PRICE_PATTERN.search(
			page_text
		)
		if discounted_match:
			total_cost = float(discounted_match.group(1).replace(",", ""))
			num_nights = int(discounted_match.group(2))
			if num_nights > 0:
				nightly_rate = round(total_cost / num_nights, 2)

	# Also try the broader TOTAL_PRICE_PATTERN which matches
	# "$X Show price breakdown for N nights" style text.
	if total_cost is None and nightly_rate is None:
		total_price_match: Union[Match[str], None] = TOTAL_PRICE_PATTERN.search(
			page_text
		)
		if total_price_match:
			total_cost = float(total_price_match.group(1).replace(",", ""))
			num_nights = int(total_price_match.group(2))
			if num_nights > 0:
				nightly_rate = round(total_cost / num_nights, 2)

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
		r"total\s*(?:(?:\(USD\)|USD)\s*)?\$(\d[\d,]*(?:\.\d{2})?)", re.IGNORECASE
	)
	total_match: Union[Match[str], None] = total_pattern.search(page_text)
	if total_match:
		total_cost = float(total_match.group(1).replace(",", ""))

	# Fallback: look for rate option format "$X total" (e.g.
	# "Non-refundable · $960.69 total").  Take the first (cheapest)
	# rate option found.
	if total_cost is None:
		rate_match: Union[Match[str], None] = RATE_OPTION_TOTAL_PATTERN.search(
			page_text
		)
		if rate_match:
			total_cost = float(rate_match.group(1).replace(",", ""))

	# Fallback: compute total from nightly rate + fees
	if total_cost is None and nightly_rate is not None:
		subtotal: float = nightly_rate * num_nights
		total_cost: float = subtotal + sum(fees.values())

	if total_cost is None:
		# Detect Airbnb "dates not available" state — the booking widget
		# shows this when the listing has no availability for the chosen
		# dates.  Provide a specific error message so the agent can skip
		# the listing rather than retrying.
		_unavailable_pattern: Pattern[str] = re.compile(
			r"(?:no\s+longer\s+available|(?:those\s+)?dates?\s+(?:are\s+)?(?:no\s+longer\s+|not\s+)available)",
			re.IGNORECASE,
		)
		if _unavailable_pattern.search(page_text):
			raise ModelRetry(
				"Listing is unavailable for the selected dates. "
				"The booking page indicates this listing is no longer "
				"available or the dates are not available. "
				"Skip this listing and move to the next one. "
				"Do NOT retry or call parse_booking_price for this listing again."
			)
		raise ModelRetry(
			"Could not extract total price from the booking page HTML. "
			"Ensure you are parsing the booking/checkout page (after "
			"clicking Reserve), not the listing page.  The booking page "
			"should contain the 'Total USD' price breakdown.  Use "
			"browser_click(element='Reserve') to navigate to the booking "
			"page, then browser_wait_for(text='Price details') before saving."
		)

	return CostBreakdown(
		total_cost=total_cost,
		num_people=num_people,
		num_nights=num_nights,
		cost_per_person=round(total_cost / max(num_people, 1), 2),
		cost_per_night=round(total_cost / max(num_nights, 1), 2),
		cost_per_night_per_person=round(
			total_cost / max(num_nights, 1) / max(num_people, 1), 2
		),
		fees=fees,
	)


def _extract_amenities(soup: BeautifulSoup) -> list[str]:
	"""Extract amenities from an Airbnb listing page via bootstrap JSON.

	Navigates the ``data-deferred-state`` bootstrap data to the
	``AMENITIES_DEFAULT`` section and extracts amenity titles from
	``seeAllAmenitiesGroups``.  Only amenities marked as ``available``
	are included.  Falls back to ``previewAmenitiesGroups`` if the
	full list is absent.

	Args:
		soup: Parsed BeautifulSoup document.

	Returns:
		A deduplicated list of available amenity names.
	"""
	bootstrap: Union[dict, None] = _extract_bootstrap_data(soup)
	if not bootstrap:
		return []

	# Navigate: niobeClientData -> [0][1] -> data.presentation
	#   .stayProductDetailPage.sections.sections -> AMENITIES_DEFAULT
	niobe: Union[list, None] = bootstrap.get("niobeClientData")
	if not isinstance(niobe, list) or not niobe:
		return []

	try:
		root: dict = niobe[0][1]
	except (IndexError, TypeError, KeyError):
		return []

	sections: Union[list, None] = None
	try:
		sections = (
			root.get("data", {})
			.get("presentation", {})
			.get("stayProductDetailPage", {})
			.get("sections", {})
			.get("sections")
		)
	except AttributeError:
		return []

	if not isinstance(sections, list):
		return []

	# Find the AMENITIES_DEFAULT section
	amenity_section: Union[dict, None] = None
	for section in sections:
		if (
			isinstance(section, dict)
			and section.get("sectionId") == "AMENITIES_DEFAULT"
		):
			amenity_section = section
			break

	if amenity_section is None:
		return []

	amenities: list[str] = []
	seen: set[str] = set()

	# Primary: seeAllAmenitiesGroups (full categorised list)
	all_groups: Union[list, None] = amenity_section.get("section", {}).get(
		"seeAllAmenitiesGroups"
	)
	if not all_groups:
		# Fallback: previewAmenitiesGroups (summary list)
		all_groups = amenity_section.get("section", {}).get("previewAmenitiesGroups")

	if isinstance(all_groups, list):
		for group in all_groups:
			if not isinstance(group, dict):
				continue
			for amenity in group.get("amenities", []):
				if not isinstance(amenity, dict):
					continue
				if not amenity.get("available", True):
					continue
				title: Union[str, None] = amenity.get("title")
				if title and title.lower() not in seen:
					seen.add(title.lower())
					amenities.append(title)

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


def parse_listing_page(
	location: str,
	html_file: Union[str, None] = None,
	page_html: Union[str, None] = None,
	num_people: int = 1,
) -> ListingWithCost:
	"""Extract listing details AND booking price from a single listing page.

	Combines :func:`parse_listing_details` and :func:`parse_booking_price`
	into a single tool call, reading the HTML only once.  This halves the
	number of agent tool calls per listing (from two to one) and ensures
	both results use the same HTML snapshot.

	Args:
		html_file: Filename relative to ``PLAYWRIGHT_OUTPUT_DIR`` or an
			absolute path to a saved HTML file.
		page_html: Raw HTML string of an Airbnb listing detail page.
		num_people: Number of people splitting the cost.  Defaults to
			``1``.

	Returns:
		A ``ListingWithCost`` containing the enriched listing metadata
		and the associated cost breakdown.

	Raises:
		ValueError: If the listing URL cannot be determined or if no
			total price can be extracted from the page.
		ValueError: If ``num_people`` is less than ``1``.
	"""
	# Resolve HTML once, then pass as raw string to both sub-parsers
	# to avoid reading the file twice.
	html_content: str = _resolve_html(html_file=html_file, page_html=page_html)

	listing: AirbnbListing = parse_listing_details(
		page_html=html_content, location=location
	)
	cost: CostBreakdown = parse_booking_price(
		page_html=html_content, num_people=num_people
	)

	return ListingWithCost(listing=listing, cost_breakdown=cost)
