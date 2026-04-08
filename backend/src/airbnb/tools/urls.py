"""Airbnb URL builder tools for search and listing pages.

Constructs properly formatted Airbnb search and listing detail URLs
with all required query parameters, including randomly generated
impression and federated search IDs.
"""

from typing import Union
from urllib.parse import quote, urlencode
from uuid import uuid4

# ── Constants ──

AIRBNB_BASE_URL = "https://www.airbnb.com"
SEARCH_PATH = "/s/{location}/homes"
LISTING_PATH = "/rooms/{room_id}"


# TODO: Add optional field for "neighborhood" to filter_listings constraints and include in search URL parameters.
# This is non-trivial because the neighborhood names in listing metadata don't always match the location strings that
# Airbnb accepts in search URLs, and many listings don't have neighborhood data at all.
# We may need to implement some kind of fuzzy matching or mapping between neighborhood names and search locations, or rely on the user to provide a valid search location that corresponds to the neighborhoods they want to target.


def build_search_url(
	location: str,
	check_in: str,
	check_out: str,
	number_of_adults: int,
) -> str:
	"""Construct an Airbnb search URL with proper query parameters.

	Generates random UUIDs for ``source_impression_id`` and
	``federated_search_id`` to mimic organic search behaviour.

	Args:
		location: City or area to search (e.g., ``"Mexico City"``).
		check_in: Check-in date as ISO 8601 string (``YYYY-MM-DD``).
		check_out: Check-out date as ISO 8601 string (``YYYY-MM-DD``).
		number_of_adults: Number of adult guests.

	Returns:
		A fully-formed Airbnb search URL string.

	Raises:
		ValueError: If ``number_of_adults`` is less than 1.
	"""
	if number_of_adults < 1:
		raise ValueError("number_of_adults must be at least 1")

	encoded_location: str = quote(location, safe="")
	path: str = SEARCH_PATH.format(location=encoded_location)

	params: dict[str, Union[str, int]] = {
		"adults": number_of_adults,
		"check_in": check_in,
		"check_out": check_out,
		"search_mode": "regular_search",
		"source_impression_id": f"p3_{uuid4().hex[:16]}",
		"previous_page_section_name": "1001",
		"federated_search_id": str(uuid4()),
	}

	return f"{AIRBNB_BASE_URL}{path}?{urlencode(params)}"


def build_listing_url(
	room_id: str,
	check_in: str,
	check_out: str,
	number_of_adults: int,
) -> str:
	"""Construct an individual Airbnb listing detail URL.

	Args:
		room_id: The Airbnb room/listing ID (numeric string).
		check_in: Check-in date as ISO 8601 string (``YYYY-MM-DD``).
		check_out: Check-out date as ISO 8601 string (``YYYY-MM-DD``).
		number_of_adults: Number of adult guests.

	Returns:
		A fully-formed Airbnb listing URL string.

	Raises:
		ValueError: If ``number_of_adults`` is less than 1.
	"""
	if number_of_adults < 1:
		raise ValueError("number_of_adults must be at least 1")

	path: str = LISTING_PATH.format(room_id=room_id)

	params: dict[str, Union[str, int]] = {
		"adults": number_of_adults,
		"check_in": check_in,
		"check_out": check_out,
		"source_impression_id": f"p3_{uuid4().hex[:16]}",
		"previous_page_section_name": "1001",
		"federated_search_id": str(uuid4()),
	}

	return f"{AIRBNB_BASE_URL}{path}?{urlencode(params)}"
