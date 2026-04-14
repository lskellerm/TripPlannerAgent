"""Airbnb URL builder tools for search and listing pages.

Constructs properly formatted Airbnb search and listing detail URLs
with all required query parameters, including randomly generated
federated search IDs.  Supports native Airbnb pre-filtering via URL
query parameters for bedrooms, bathrooms, amenities, room type, and
price range.

.. note::

   Airbnb uses **different** date parameter names depending on
   the endpoint:

   * Search pages (``/s/.../homes``): ``checkin`` / ``checkout``
   * Listing pages (``/rooms/...``): ``check_in`` / ``check_out``
"""

from datetime import date
from typing import Union
from urllib.parse import quote, urlencode
from uuid import uuid4

from src.airbnb.constants import AIRBNB_AMENITY_IDS

# ── Constants ──

AIRBNB_BASE_URL = "https://www.airbnb.com"
SEARCH_PATH = "/s/{location}/homes"
LISTING_PATH = "/rooms/{room_id}"


def build_search_url(
	location: str,
	check_in: str,
	check_out: str,
	number_of_adults: int,
	min_bedrooms: Union[int, None] = None,
	min_bathrooms: Union[int, None] = None,
	min_beds: Union[int, None] = None,
	required_amenities: Union[list[str], None] = None,
	room_type: Union[str, None] = None,
	price_min: Union[int, None] = None,
	price_max: Union[int, None] = None,
) -> str:
	"""Construct an Airbnb search URL with proper query parameters.

	Generates random UUIDs for ``source_impression_id`` and
	``federated_search_id`` to mimic organic search behaviour.

	Optional pre-filtering parameters leverage Airbnb's native
	server-side filtering — the search results page will only show
	listings that match the specified criteria, reducing the number
	of irrelevant results the agent needs to explore.

	Args:
		location: City or area to search (e.g., ``"Mexico City"``).
		check_in: Check-in date as ISO 8601 string (``YYYY-MM-DD``).
		check_out: Check-out date as ISO 8601 string (``YYYY-MM-DD``).
		number_of_adults: Number of adult guests.
		min_bedrooms: Minimum number of bedrooms to filter by.
		min_bathrooms: Minimum number of bathrooms to filter by.
		min_beds: Minimum number of beds to filter by.
		required_amenities: List of amenity names to require (e.g.,
			``["wifi", "ac", "kitchen"]``).  Names are resolved to
			Airbnb's numeric amenity IDs via ``AIRBNB_AMENITY_IDS``.
			Unknown amenity names are silently skipped.
		room_type: Airbnb room type filter.  One of ``"Entire home/apt"``,
			``"Private room"``, or ``"Shared room"``.  Maps to Airbnb's
			``room_types[]`` parameter.
		price_min: Minimum price per night in USD.
		price_max: Maximum price per night in USD.

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
		"refinement_paths[]": "/homes",
		"query": location,
		"checkin": check_in,
		"checkout": check_out,
		"search_mode": "regular_search",
		"channel": "EXPLORE",
		"federated_search_id": str(uuid4()),
	}

	# ── Native Airbnb pre-filters ──
	if min_bedrooms is not None and min_bedrooms > 0:
		params["min_bedrooms"] = min_bedrooms

	if min_bathrooms is not None and min_bathrooms > 0:
		params["min_bathrooms"] = min_bathrooms

	if min_beds is not None and min_beds > 0:
		params["min_beds"] = min_beds

	has_price_filter: bool = False
	if price_min is not None and price_min > 0:
		params["price_min"] = price_min
		has_price_filter = True

	if price_max is not None and price_max > 0:
		params["price_max"] = price_max
		has_price_filter = True

	if has_price_filter:
		params["price_filter_input_type"] = 2
		num_nights: int = (
			date.fromisoformat(check_out) - date.fromisoformat(check_in)
		).days
		if num_nights > 0:
			params["price_filter_num_nights"] = num_nights

	# Room type mapping
	_ROOM_TYPE_MAP: dict[str, str] = {
		"entire home/apt": "Entire home/apt",
		"entire home": "Entire home/apt",
		"entire_home": "Entire home/apt",
		"entire": "Entire home/apt",
		"private room": "Private room",
		"private_room": "Private room",
		"private": "Private room",
		"shared room": "Shared room",
		"shared_room": "Shared room",
		"shared": "Shared room",
	}
	if room_type is not None:
		mapped: Union[str, None] = _ROOM_TYPE_MAP.get(room_type.lower())
		if mapped is not None:
			params["room_types[]"] = mapped

	# Build the base URL with standard params
	url: str = f"{AIRBNB_BASE_URL}{path}?{urlencode(params)}"

	# Amenity IDs are appended as repeated ``amenities[]=ID`` params
	if required_amenities:
		amenity_ids: list[int] = []
		seen_ids: set[int] = set()
		for amenity in required_amenities:
			aid: Union[int, None] = AIRBNB_AMENITY_IDS.get(amenity.lower())
			if aid is not None and aid not in seen_ids:
				amenity_ids.append(aid)
				seen_ids.add(aid)
		if amenity_ids:
			amenity_params: str = "&".join(
				f"amenities%5B%5D={aid}" for aid in amenity_ids
			)
			url = f"{url}&{amenity_params}"

	return url


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
