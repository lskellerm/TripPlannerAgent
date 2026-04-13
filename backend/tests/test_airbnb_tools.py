"""Tests for Airbnb domain tools — URLs, parsers, and analysis functions."""

from datetime import date
from pathlib import Path

import pytest
from pydantic_ai.exceptions import ModelRetry

from src.agent.schemas import TripWeek
from src.airbnb.schemas import (
	AirbnbListing,
	CostBreakdown,
	ListingWithCost,
	WeekAnalysis,
)
from src.airbnb.tools.analysis import (
	calculate_cost_breakdown,
	calculate_trip_totals,
	filter_listings,
	rank_by_category,
)
from src.airbnb.tools.parsers import (
	_normalize_neighborhood,
	_scan_for_known_neighborhoods,
	_unwrap_json_string,
	parse_booking_price,
	parse_listing_details,
	parse_listing_page,
	parse_search_results,
)
from src.airbnb.tools.urls import build_listing_url, build_search_url

# ── Paths to discovery HTML fixtures ──

DISCOVERY_HTML_DIR: Path = (
	Path(__file__).resolve().parent.parent.parent / "discovery" / "html"
)
SEARCH_PAGE_HTML: Path = DISCOVERY_HTML_DIR / "AirBnB_example_search_page.html"
LISTING_PAGE_HTML: Path = (
	DISCOVERY_HTML_DIR
	/ "Steps from Reforma 3BR_3BA w_View, AC, W_D _ Rio 6 - Apartments for Rent in Mexico City, Mexico City, Mexico - Airbnb.html"
)


# ── Shared Fixtures ──


@pytest.fixture
def sample_listing_a() -> AirbnbListing:
	"""Listing A — Steps from Reforma (best reviews)."""
	return AirbnbListing(
		url="https://www.airbnb.com/rooms/863180984181188292",
		title="Steps from Reforma 3BR/3BA w/View, AC, W/D | Rio 6",
		total_cost=1542.66,
		nightly_rate=220.38,
		num_beds=3,
		num_bedrooms=3,
		num_bathrooms=3,
		amenities=["Air conditioning", "washer/dryer", "Wi-Fi"],
		neighborhood="Colonia Renacimiento/Cuauhtémoc",
		rating=4.91,
		num_reviews=126,
	)


@pytest.fixture
def sample_listing_b() -> AirbnbListing:
	"""Listing B — Incredible apartment (best amenities)."""
	return AirbnbListing(
		url="https://www.airbnb.com/rooms/947792677512707552",
		title="Incredible apartment in Roma",
		total_cost=1382.48,
		nightly_rate=197.50,
		num_beds=3,
		num_bedrooms=3,
		num_bathrooms=2,
		amenities=["Air conditioning", "washer/dryer", "Wi-Fi", "gym", "cowork space"],
		neighborhood="Roma Sur",
		rating=4.83,
		num_reviews=84,
	)


@pytest.fixture
def sample_listing_c() -> AirbnbListing:
	"""Listing C — WFH Oasis (cheapest, best rating)."""
	return AirbnbListing(
		url="https://www.airbnb.com/rooms/999999999",
		title="2BR WFH Oasis: AC + views",
		total_cost=1382.48,
		nightly_rate=197.50,
		num_beds=3,
		num_bedrooms=3,
		num_bathrooms=2,
		amenities=["Air conditioning", "washer/dryer", "Wi-Fi", "gym", "cowork space"],
		neighborhood="Roma Sur",
		rating=4.95,
		num_reviews=86,
	)


@pytest.fixture
def cost_a() -> CostBreakdown:
	"""Cost breakdown for listing A ($1542.66, 4 people, 7 nights)."""
	return CostBreakdown(
		total_cost=1542.66,
		num_people=4,
		num_nights=7,
		cost_per_person=385.67,
		cost_per_night=220.38,
		cost_per_night_per_person=55.10,
		fees={"cleaning_fee": 50.0, "service_fee": 120.0},
	)


@pytest.fixture
def cost_b() -> CostBreakdown:
	"""Cost breakdown for listing B ($1382.48, 4 people, 7 nights)."""
	return CostBreakdown(
		total_cost=1382.48,
		num_people=4,
		num_nights=7,
		cost_per_person=345.62,
		cost_per_night=197.50,
		cost_per_night_per_person=49.37,
		fees={},
	)


@pytest.fixture
def cost_c() -> CostBreakdown:
	"""Cost breakdown for listing C ($1382.48, 4 people, 7 nights)."""
	return CostBreakdown(
		total_cost=1382.48,
		num_people=4,
		num_nights=7,
		cost_per_person=345.62,
		cost_per_night=197.50,
		cost_per_night_per_person=49.37,
		fees={},
	)


@pytest.fixture
def lwc_a(sample_listing_a: AirbnbListing, cost_a: CostBreakdown) -> ListingWithCost:
	"""ListingWithCost for listing A."""
	return ListingWithCost(listing=sample_listing_a, cost_breakdown=cost_a)


@pytest.fixture
def lwc_b(sample_listing_b: AirbnbListing, cost_b: CostBreakdown) -> ListingWithCost:
	"""ListingWithCost for listing B."""
	return ListingWithCost(listing=sample_listing_b, cost_breakdown=cost_b)


@pytest.fixture
def lwc_c(sample_listing_c: AirbnbListing, cost_c: CostBreakdown) -> ListingWithCost:
	"""ListingWithCost for listing C."""
	return ListingWithCost(listing=sample_listing_c, cost_breakdown=cost_c)


@pytest.fixture
def week1_constraints() -> TripWeek:
	"""Week 1 constraints — 3 people, 2BR, Roma Norte."""
	return TripWeek(
		week_label="Week 1",
		check_in=date(2026, 4, 24),
		check_out=date(2026, 5, 2),
		location="Mexico City",
		neighborhood_constraints=["Roma Norte"],
		participants=["Karina", "Luis", "Mom"],
		num_people=3,
		min_bedrooms=2,
		min_bathrooms=1,
		min_rating=4.5,
		required_amenities=["Wi-Fi"],
		max_price_per_person=570.66,
	)


@pytest.fixture
def week2_constraints() -> TripWeek:
	"""Week 2 constraints — 4 people, 3BR."""
	return TripWeek(
		week_label="Week 2",
		check_in=date(2026, 5, 2),
		check_out=date(2026, 5, 9),
		location="Mexico City",
		participants=["Karina", "Luis", "Mom", "Laura"],
		num_people=4,
		min_bedrooms=3,
		min_bathrooms=2,
		min_rating=4.5,
		required_amenities=["Wi-Fi"],
		max_price_per_person=550.0,
	)


# ══════════════════════════════════════════════════════════════
# URL Builder Tests
# ══════════════════════════════════════════════════════════════


class TestBuildSearchUrl:
	"""Verify Airbnb search URL construction."""

	def test_basic_url_format(self) -> None:
		"""URL follows the documented Airbnb search format."""
		url: str = build_search_url(
			location="Mexico City",
			check_in="2026-05-02",
			check_out="2026-05-09",
			number_of_adults=4,
		)
		assert url.startswith("https://www.airbnb.com/s/")
		assert "Mexico%20City" in url
		assert "adults=4" in url
		assert "check_in=2026-05-02" in url
		assert "check_out=2026-05-09" in url
		assert "search_mode=regular_search" in url
		assert "source_impression_id=" in url
		assert "federated_search_id=" in url
		assert "previous_page_section_name=1001" in url

	def test_unique_impression_ids(self) -> None:
		"""Each call generates different impression and search IDs."""
		url1: str = build_search_url("CDMX", "2026-05-02", "2026-05-09", 2)
		url2: str = build_search_url("CDMX", "2026-05-02", "2026-05-09", 2)
		# Extract the impression IDs — they should differ
		assert url1 != url2

	def test_location_encoding(self) -> None:
		"""Location with special characters is URL-encoded."""
		url: str = build_search_url(
			location="Juárez, Mexico City",
			check_in="2026-05-02",
			check_out="2026-05-09",
			number_of_adults=2,
		)
		assert "Ju%C3%A1rez%2C%20Mexico%20City" in url

	def test_invalid_num_adults_raises(self) -> None:
		"""Zero or negative adults raises ValueError."""
		with pytest.raises(ValueError, match="number_of_adults must be at least 1"):
			build_search_url("CDMX", "2026-05-02", "2026-05-09", 0)

		with pytest.raises(ValueError, match="number_of_adults must be at least 1"):
			build_search_url("CDMX", "2026-05-02", "2026-05-09", -1)


class TestBuildListingUrl:
	"""Verify Airbnb listing URL construction."""

	def test_basic_url_format(self) -> None:
		"""URL follows the documented Airbnb listing format."""
		url: str = build_listing_url(
			room_id="863180984181188292",
			check_in="2026-05-02",
			check_out="2026-05-09",
			number_of_adults=4,
		)
		assert url.startswith("https://www.airbnb.com/rooms/863180984181188292")
		assert "adults=4" in url
		assert "check_in=2026-05-02" in url
		assert "check_out=2026-05-09" in url

	def test_invalid_num_adults_raises(self) -> None:
		"""Zero or negative adults raises ValueError."""
		with pytest.raises(ValueError, match="number_of_adults must be at least 1"):
			build_listing_url("12345", "2026-05-02", "2026-05-09", 0)


# ══════════════════════════════════════════════════════════════
# Parser Tests
# ══════════════════════════════════════════════════════════════


class TestParseSearchResults:
	"""Verify search results HTML parsing."""

	def test_returns_list(self) -> None:
		"""Parser always returns a list (may be empty for SPA pages)."""
		result: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html="<html><body>No listings</body></html>"
		)
		assert isinstance(result, list)

	def test_extracts_listings_from_links(self) -> None:
		"""Parser extracts listings from anchor tags with /rooms/ hrefs."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/12345?adults=2">
				<div>
					<h2>Cozy Apartment</h2>
					<span>$150 per night</span>
					<span>4.85 stars</span>
					<span>42 reviews</span>
				</div>
			</a>
			<a href="/rooms/67890?adults=2">
				<div>
					<h2>Luxury Suite</h2>
					<span>$300 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 2
		assert listings[0].url == "https://www.airbnb.com/rooms/12345?adults=2"
		assert listings[1].url == "https://www.airbnb.com/rooms/67890?adults=2"

	def test_deduplicates_by_room_id(self) -> None:
		"""Duplicate room IDs are only included once."""
		html = """
		<html><body>
		<a href="/rooms/12345?v1">Link 1</a>
		<a href="/rooms/12345?v2">Link 2</a>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1

	def test_search_page_fixture(self) -> None:
		"""Parser runs without error on the saved search page fixture."""
		if not SEARCH_PAGE_HTML.exists():
			pytest.skip("Search page HTML fixture not found")
		html: str = SEARCH_PAGE_HTML.read_text(encoding="utf-8")
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert isinstance(listings, list)
		# Airbnb SPA pages may yield 0 listings from raw HTML
		for listing in listings:
			assert isinstance(listing, AirbnbListing)
			assert listing.url.startswith("https://www.airbnb.com/rooms/")

	def test_extracts_nightly_rate(self) -> None:
		"""Parser extracts nightly rate from listing card text."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/11111">
				<div><span>$220 per night</span></div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].nightly_rate == 220.0

	def test_extracts_beds_and_bedrooms_from_subtitle(self) -> None:
		"""Parser extracts num_beds and num_bedrooms from card subtitle elements."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/22222">
				<div>
					<h2>Cozy Apartment</h2>
					<span data-testid="listing-card-subtitle">2 bedrooms 2 bedrooms 2 beds , · 2 beds</span>
					<span>$150 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].num_bedrooms == 2
		assert listings[0].num_beds == 2

	def test_extracts_beds_only_from_subtitle(self) -> None:
		"""Parser extracts num_beds when subtitle only mentions beds, not bedrooms."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/33333">
				<div>
					<h2>Studio</h2>
					<span data-testid="listing-card-subtitle">1 bed</span>
					<span>$80 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].num_beds == 1
		assert listings[0].num_bedrooms is None

	def test_extracts_location_from_card_title(self) -> None:
		"""Parser extracts neighborhood from listing-card-title 'Apartment in City'."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/44444">
				<div>
					<div data-testid="listing-card-title">Apartment in Mexico City</div>
					<span>$150 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].neighborhood == "Mexico City"

	def test_extracts_neighborhood_from_subtitle(self) -> None:
		"""Parser extracts neighborhood from a data-testid subtitle element."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/22222">
				<div>
					<h2>Cozy Apartment</h2>
					<span data-testid="listing-card-title">Roma Norte · Entire rental unit</span>
					<span>$150 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].neighborhood == "Roma Norte"

	def test_extracts_neighborhood_from_separator_text(self) -> None:
		"""Parser extracts neighborhood from middle-dot separator text in card."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/33333">
				<div>
					<h2>Modern Studio</h2>
					<span>Condesa · Private room · 1 bed</span>
					<span>$90 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].neighborhood == "Condesa"

	def test_neighborhood_none_when_not_present(self) -> None:
		"""Neighborhood is None when no separator-based location text is found."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/44444">
				<div>
					<h2>Plain Listing</h2>
					<span>$100 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].neighborhood is None

	def test_keyword_scan_finds_neighborhood_in_host_title(self) -> None:
		"""When no subtitle/card-title provides a neighbourhood, keyword scan on the
		host-given listing name finds known CDMX names."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/77777">
				<div>
					<h2>Beautiful, Cozy, Heart Condesa</h2>
					<span>$120 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].neighborhood == "Condesa"

	def test_normalizes_abbreviation_from_subtitle(self) -> None:
		"""Neighbourhood abbreviation in subtitle is normalised via CDMX map."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/88888">
				<div>
					<h2>Great Apartment</h2>
					<span>Roma Nte · Entire rental unit</span>
					<span>$100 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].neighborhood == "Roma Norte"

	def test_extracts_total_cost_and_nightly_from_stay_price(self) -> None:
		"""Parser extracts total cost and computes nightly rate from 'N nights' text."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/55555">
				<div>
					<h2>Beach House</h2>
					<span>$700 Show price breakdown for 7 nights</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].total_cost == 700.0
		assert listings[0].nightly_rate == 100.0

	def test_unwrap_json_string_decodes_wrapped_html(self) -> None:
		"""_unwrap_json_string decodes JSON-stringified HTML from browser_evaluate."""
		raw = '"<html><body>Hello \\"world\\"</body></html>"'
		result: str = _unwrap_json_string(raw)
		assert result == '<html><body>Hello "world"</body></html>'

	def test_unwrap_json_string_passes_through_normal_html(self) -> None:
		"""_unwrap_json_string returns normal HTML unchanged."""
		html = "<html><body>Hello</body></html>"
		assert _unwrap_json_string(html) == html

	def test_parse_search_results_with_json_wrapped_html(self) -> None:
		"""Parser handles JSON-stringified HTML (as saved by browser_evaluate)."""
		inner = '<html><body><div><a href="/rooms/99999"><div><h2>Wrapped Listing</h2><span>$200 per night</span></div></a></div></body></html>'
		import orjson

		json_wrapped: str = orjson.dumps(inner).decode("utf-8")
		# json_wrapped is '"<html>..."' — a JSON string
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=json_wrapped
		)
		# page_html path doesn't go through _unwrap_json_string — only html_file does.
		# This tests that the link extraction works on properly formatted HTML.
		# For JSON-unwrapped content we test via _unwrap_json_string directly.
		assert isinstance(listings, list)

	def test_skips_listing_name_containing_bed_keyword(self) -> None:
		"""Parser skips subtitles where 'bed' appears in listing name, not bed info.

		Regression test: listing names like "Brand New 2-Bedroom ..." contain
		"bed" but don't match the structured bed-count regex.  The parser must
		continue to the next subtitle (with actual bed info) instead of breaking.
		"""
		html = """
		<html><body>
		<div>
			<a href="/rooms/69425">
				<div>
					<h2>Cozy Apartment</h2>
					<span data-testid="listing-card-subtitle"></span>
					<span data-testid="listing-card-subtitle">Brand New 2-Bedroom in the Heart of Trendy Roma</span>
					<span data-testid="listing-card-subtitle">2 bedrooms 2 bedrooms 2 beds , · 2 beds</span>
					<span data-testid="listing-card-subtitle"></span>
					<span data-testid="listing-card-subtitle"></span>
					<span>$150 per night</span>
				</div>
			</a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 1
		assert listings[0].num_bedrooms == 2
		assert listings[0].num_beds == 2

	def test_excludes_available_for_similar_dates_listings(self) -> None:
		"""Parser excludes listings from the 'Available for similar dates' carousel.

		Airbnb search pages sometimes append a carousel of listings with
		different check-in/check-out dates.  These must be excluded because
		they don't match the user's requested dates and will fail at booking.
		"""
		html = """
		<html><body>
		<!-- Primary search results -->
		<div>
			<a href="/rooms/11111?check_in=2026-04-15&check_out=2026-04-22">
				<div><h2>Primary Listing A</h2><span>$500 for 7 nights</span></div>
			</a>
		</div>
		<div>
			<a href="/rooms/22222?check_in=2026-04-15&check_out=2026-04-22">
				<div><h2>Primary Listing B</h2><span>$600 for 7 nights</span></div>
			</a>
		</div>
		<!-- "Available for similar dates" carousel — different dates -->
		<div role="group">
			<div><h2>Available for similar dates</h2></div>
			<div>
				<a href="/rooms/33333?check_in=2026-04-17&check_out=2026-04-21">
					<div><h2>Similar Dates Listing</h2><span>$300 for 4 nights</span></div>
				</a>
			</div>
			<div>
				<a href="/rooms/44444?check_in=2026-04-18&check_out=2026-04-22">
					<div><h2>Another Similar Listing</h2><span>$400 for 4 nights</span></div>
				</a>
			</div>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		room_ids = {
			listing.url.split("/rooms/")[1].split("?")[0] for listing in listings
		}
		assert room_ids == {"11111", "22222"}
		assert len(listings) == 2

	def test_no_similar_dates_section_returns_all(self) -> None:
		"""When there is no 'Available for similar dates' section, all listings are returned."""
		html = """
		<html><body>
		<div>
			<a href="/rooms/55555"><div><h2>Listing One</h2><span>$400 per night</span></div></a>
		</div>
		<div>
			<a href="/rooms/66666"><div><h2>Listing Two</h2><span>$500 per night</span></div></a>
		</div>
		</body></html>
		"""
		listings: list[AirbnbListing] = parse_search_results(
			location="Mexico City", page_html=html
		)
		assert len(listings) == 2


class TestParseListingDetails:
	"""Verify listing detail page parsing."""

	def test_extracts_from_meta_tags(self) -> None:
		"""Parser extracts title and URL from meta tags."""
		html = """
		<html><head>
			<meta property="og:url" content="https://www.airbnb.com/rooms/12345" />
			<meta property="og:title" content="Beautiful Loft in Roma Norte" />
		</head><body>
			<h1>Beautiful Loft in Roma Norte</h1>
			<div>3 bedrooms · 2 bathrooms</div>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.url == "https://www.airbnb.com/rooms/12345"
		assert listing.title == "Beautiful Loft in Roma Norte"
		assert listing.num_bedrooms == 3
		assert listing.num_bathrooms == 2

	def test_extracts_room_data_from_og_title(self) -> None:
		"""Parser extracts bedrooms, beds, baths from og:title format."""
		html = """
		<html><head>
			<meta property="og:url" content="https://www.airbnb.com/rooms/10883847" />
			<meta property="og:title" content="Home in Mexico City · ★4.88 · 1 bedroom · 1 bed · 1 private bath" />
		</head><body></body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.num_bedrooms == 1
		assert listing.num_beds == 1
		assert listing.num_bathrooms == 1

	def test_extracts_room_data_multiple_from_og_title(self) -> None:
		"""Parser correctly extracts multi-digit room counts from og:title."""
		html = """
		<html><head>
			<meta property="og:url" content="https://www.airbnb.com/rooms/99999" />
			<meta property="og:title" content="Condo in CDMX · 3 bedrooms · 4 beds · 2 shared baths" />
		</head><body></body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.num_bedrooms == 3
		assert listing.num_beds == 4
		assert listing.num_bathrooms == 2

	def test_og_title_takes_priority_over_body(self) -> None:
		"""og:title room data takes priority over page body text."""
		html = """
		<html><head>
			<meta property="og:url" content="https://www.airbnb.com/rooms/55555" />
			<meta property="og:title" content="Home in CDMX · 2 bedrooms · 3 beds · 1 bath" />
		</head><body>
			<div>5 bedrooms · 4 bathrooms</div>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.num_bedrooms == 2
		assert listing.num_beds == 3
		assert listing.num_bathrooms == 1

	def test_extracts_from_json_ld(self) -> None:
		"""Parser extracts rating and reviews from JSON-LD."""
		html = """
		<html><head>
			<meta property="og:url" content="https://www.airbnb.com/rooms/12345" />
			<script type="application/ld+json">
			{
				"@type": "Product",
				"name": "Test Listing",
				"aggregateRating": {
					"ratingValue": 4.91,
					"reviewCount": 126
				}
			}
			</script>
		</head><body></body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.rating == 4.91
		assert listing.num_reviews == 126

	def test_raises_on_missing_url(self) -> None:
		"""Parser raises ValueError if no URL can be found."""
		with pytest.raises(ValueError, match="Could not determine listing URL"):
			parse_listing_details(
				location="Mexico City", page_html="<html><body>No URL</body></html>"
			)

	def test_listing_page_fixture(self) -> None:
		"""Parser runs without error on the saved listing page fixture."""
		if not LISTING_PAGE_HTML.exists():
			pytest.skip("Listing page HTML fixture not found")
		html: str = LISTING_PAGE_HTML.read_text(encoding="utf-8")
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert isinstance(listing, AirbnbListing)
		assert "airbnb.com/rooms/" in listing.url


class TestParseBookingPrice:
	"""Verify booking price breakdown parsing."""

	def test_extracts_total_and_nightly_rate(self) -> None:
		"""Parser extracts total, nightly rate, and fees."""
		html = """
		<html><body>
		<div>
			<div>$220.38 x 7 nights</div>
			<div>Cleaning fee $50.00</div>
			<div>Service fee $120.00</div>
			<div>Total (USD) $1,542.66</div>
		</div>
		</body></html>
		"""
		breakdown: CostBreakdown = parse_booking_price(page_html=html)
		assert breakdown.total_cost == 1542.66
		assert breakdown.num_nights == 7
		assert breakdown.fees.get("cleaning_fee") == 50.0
		assert breakdown.fees.get("service_fee") == 120.0

	def test_raises_on_missing_price(self) -> None:
		"""Parser raises ModelRetry when no price is found."""
		with pytest.raises(ModelRetry, match="Could not extract total price"):
			parse_booking_price(page_html="<html><body>No price</body></html>")

	def test_raises_descriptive_error_when_dates_not_available(self) -> None:
		"""Parser detects 'dates not available' and raises a specific message."""
		html = """
		<html><body>
		<div data-testid="book-it-default">
			Check-in 4/15/2026 Checkout 4/22/2026
			Guests 2 guests
			Those dates are not available
			Change dates
		</div>
		</body></html>
		"""
		with pytest.raises(ModelRetry, match="unavailable for the selected dates"):
			parse_booking_price(page_html=html)

	def test_raises_dates_not_available_variant_wording(self) -> None:
		"""Parser detects variant wording of date unavailability."""
		html = """
		<html><body>
		<div>Date not available</div>
		</body></html>
		"""
		with pytest.raises(ModelRetry, match="unavailable for the selected dates"):
			parse_booking_price(page_html=html)

	def test_fallback_to_computed_total(self) -> None:
		"""When no explicit total, compute from nightly rate + fees."""
		html = """
		<html><body>
		<div>$200.00 x 3 nights</div>
		<div>Cleaning fee $50.00</div>
		</body></html>
		"""
		breakdown: CostBreakdown = parse_booking_price(page_html=html)
		# 200 * 3 + 50 = 650
		assert breakdown.total_cost == 650.0
		assert breakdown.num_nights == 3

	def test_extracts_for_n_nights_format(self) -> None:
		"""Parser extracts price from '$X for N nights' format."""
		html = """
		<html><body>
		<div>$344 for 7 nights</div>
		</body></html>
		"""
		breakdown: CostBreakdown = parse_booking_price(page_html=html)
		assert breakdown.total_cost == 344.0
		assert breakdown.num_nights == 7
		assert breakdown.cost_per_night == round(344.0 / 7, 2)

	def test_extracts_show_price_breakdown_format(self) -> None:
		"""Parser extracts price from '$X Show price breakdown for N nights'."""
		html = """
		<html><body>
		<div>$1,200 Show price breakdown for 5 nights</div>
		</body></html>
		"""
		breakdown: CostBreakdown = parse_booking_price(page_html=html)
		assert breakdown.total_cost == 1200.0
		assert breakdown.num_nights == 5
		assert breakdown.cost_per_night == 240.0

	def test_x_nights_format_preferred_over_for_n_nights(self) -> None:
		"""The '$X x N nights' format takes priority when both are present."""
		html = """
		<html><body>
		<div>$100.00 x 7 nights</div>
		<div>$800 for 7 nights</div>
		<div>Total (USD) $750.00</div>
		</body></html>
		"""
		breakdown: CostBreakdown = parse_booking_price(page_html=html)
		# $100/night x 7 = $700 base, Total = $750 (from explicit Total line)
		assert breakdown.total_cost == 750.0
		assert breakdown.num_nights == 7

	def test_real_listing_html_extracts_price(self) -> None:
		"""Integration test: real HTML from listing extracts price data."""
		html_path = Path(__file__).resolve().parent.parent / "listing_15326965.html"
		if not html_path.exists():
			pytest.skip("listing_15326965.html not available")
		breakdown: CostBreakdown = parse_booking_price(html_file=str(html_path))
		assert breakdown.total_cost == 366.0
		assert breakdown.num_nights == 5

	def test_listing_unavailable_sentinel_raises(self) -> None:
		"""Parser raises clear error when booking HTML contains the LISTING_UNAVAILABLE sentinel."""
		with pytest.raises(ModelRetry, match="LISTING_UNAVAILABLE"):
			parse_booking_price(page_html="LISTING_UNAVAILABLE")

	def test_listing_unavailable_sentinel_json_wrapped(self) -> None:
		"""Parser handles JSON-stringified LISTING_UNAVAILABLE from browser_evaluate."""
		with pytest.raises(ModelRetry, match="LISTING_UNAVAILABLE"):
			parse_booking_price(page_html='"LISTING_UNAVAILABLE"')

	def test_no_longer_available_text_raises(self) -> None:
		"""Parser detects 'no longer available' text on booking pages."""
		html = """
		<html><body>
		<h2>This place is no longer available</h2>
		<p>Edit your dates to get updated pricing</p>
		</body></html>
		"""
		with pytest.raises(ModelRetry, match="unavailable"):
			parse_booking_price(page_html=html)


# ══════════════════════════════════════════════════════════════
# Analysis Tools Tests
# ══════════════════════════════════════════════════════════════


class TestCalculateCostBreakdown:
	"""Verify cost breakdown calculations."""

	def test_reference_values(self) -> None:
		"""Matches CDMX reference: $1542.66 / 4 people / 7 nights."""
		result: CostBreakdown = calculate_cost_breakdown(
			total_cost=1542.66, num_people=4, num_nights=7
		)
		assert result.total_cost == 1542.66
		assert result.num_people == 4
		assert result.num_nights == 7
		assert result.cost_per_person == 385.67  # round(1542.66 / 4, 2)
		assert result.cost_per_night == 220.38  # round(1542.66 / 7, 2)
		assert result.cost_per_night_per_person == 55.10  # round(1542.66/4/7, 2)

	def test_three_person_split(self) -> None:
		"""Cost for 3 people: $1542.66 / 3 = $514.22."""
		result: CostBreakdown = calculate_cost_breakdown(
			total_cost=1542.66, num_people=3, num_nights=7
		)
		assert result.cost_per_person == 514.22

	def test_fees_passed_through(self) -> None:
		"""Fees dict is stored as-is on the breakdown."""
		fees: dict[str, int | float] = {"cleaning_fee": 50.0, "service_fee": 120.0}
		result: CostBreakdown = calculate_cost_breakdown(
			total_cost=1000.0, num_people=2, num_nights=5, fees=fees
		)
		assert result.fees == fees

	def test_defaults_to_empty_fees(self) -> None:
		"""No fees argument defaults to empty dict."""
		result = calculate_cost_breakdown(total_cost=500.0, num_people=1, num_nights=1)
		assert result.fees == {}

	def test_invalid_num_people_raises(self) -> None:
		"""Zero or negative people raises ValueError."""
		with pytest.raises(ValueError, match="num_people must be at least 1"):
			calculate_cost_breakdown(total_cost=100.0, num_people=0, num_nights=1)

	def test_invalid_num_nights_raises(self) -> None:
		"""Zero or negative nights raises ValueError."""
		with pytest.raises(ValueError, match="num_nights must be at least 1"):
			calculate_cost_breakdown(total_cost=100.0, num_people=1, num_nights=0)


class TestFilterListings:
	"""Verify listing filtering against constraints."""

	def test_all_pass(
		self,
		lwc_a: ListingWithCost,
		lwc_b: ListingWithCost,
	) -> None:
		"""Listings matching all constraints are kept."""
		constraints = TripWeek(
			week_label="Test",
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			participants=["A", "B"],
			num_people=2,
			min_bedrooms=2,
			min_bathrooms=1,
			min_rating=4.0,
		)
		result: list[ListingWithCost] = filter_listings([lwc_a, lwc_b], constraints)
		assert len(result) == 2

	def test_filter_by_bedrooms(
		self,
		lwc_a: ListingWithCost,
	) -> None:
		"""Listing with insufficient bedrooms is excluded."""
		constraints = TripWeek(
			week_label="Test",
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			participants=["A"],
			num_people=1,
			min_bedrooms=5,  # Listing A has 3
			min_bathrooms=1,
		)
		result: list[ListingWithCost] = filter_listings([lwc_a], constraints)
		assert len(result) == 0

	def test_filter_by_rating(
		self,
		lwc_a: ListingWithCost,
	) -> None:
		"""Listing below min rating is excluded."""
		constraints = TripWeek(
			week_label="Test",
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			participants=["A"],
			num_people=1,
			min_bedrooms=1,
			min_bathrooms=1,
			min_rating=4.95,  # Listing A has 4.91
		)
		result: list[ListingWithCost] = filter_listings([lwc_a], constraints)
		assert len(result) == 0

	def test_filter_by_amenities(
		self,
		lwc_a: ListingWithCost,
	) -> None:
		"""Listing missing required amenities is excluded."""
		constraints = TripWeek(
			week_label="Test",
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			participants=["A"],
			num_people=1,
			min_bedrooms=1,
			min_bathrooms=1,
			required_amenities=["pool"],  # Listing A doesn't have a pool
		)
		result: list[ListingWithCost] = filter_listings([lwc_a], constraints)
		assert len(result) == 0

	def test_filter_by_neighborhood(
		self,
		lwc_b: ListingWithCost,
	) -> None:
		"""Listing in wrong neighbourhood is excluded."""
		constraints = TripWeek(
			week_label="Test",
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			neighborhood_constraints=["Roma Norte"],  # Listing B is Roma Sur
			participants=["A"],
			num_people=1,
			min_bedrooms=1,
			min_bathrooms=1,
		)
		result: list[ListingWithCost] = filter_listings([lwc_b], constraints)
		assert len(result) == 0

	def test_filter_by_max_price(
		self,
		lwc_a: ListingWithCost,
	) -> None:
		"""Listing exceeding max price per person is excluded."""
		constraints = TripWeek(
			week_label="Test",
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			participants=["A"],
			num_people=1,
			min_bedrooms=1,
			min_bathrooms=1,
			max_price_per_person=300.0,  # Listing A cost_per_person = 385.67
		)
		result: list[ListingWithCost] = filter_listings([lwc_a], constraints)
		assert len(result) == 0

	def test_amenity_check_case_insensitive(
		self,
		lwc_a: ListingWithCost,
	) -> None:
		"""Amenity matching is case-insensitive."""
		constraints = TripWeek(
			week_label="Test",
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			participants=["A"],
			num_people=1,
			min_bedrooms=1,
			min_bathrooms=1,
			required_amenities=["wi-fi"],  # Listing A has "Wi-Fi"
		)
		result: list[ListingWithCost] = filter_listings([lwc_a], constraints)
		assert len(result) == 1


class TestRankByCategory:
	"""Verify categorical ranking of listings."""

	def test_empty_listings(self) -> None:
		"""Empty input returns all-None categories."""
		result: dict[str, ListingWithCost | None] = rank_by_category([])
		assert result["best_price"] is None
		assert result["best_value"] is None
		assert result["best_amenities"] is None
		assert result["best_location"] is None
		assert result["best_reviews"] is None

	def test_single_listing(self, lwc_a: ListingWithCost) -> None:
		"""Single listing is best in all applicable categories."""
		result: dict[str, ListingWithCost | None] = rank_by_category([lwc_a])
		assert result["best_price"] is lwc_a
		assert result["best_value"] is lwc_a
		assert result["best_reviews"] is lwc_a

	def test_best_price(
		self,
		lwc_a: ListingWithCost,
		lwc_b: ListingWithCost,
	) -> None:
		"""Best price selects the lowest total cost."""
		result: dict[str, ListingWithCost | None] = rank_by_category([lwc_a, lwc_b])
		# lwc_b has $1382.48 < lwc_a $1542.66
		assert result["best_price"] is lwc_b

	def test_best_amenities(
		self,
		lwc_a: ListingWithCost,
		lwc_b: ListingWithCost,
	) -> None:
		"""Best amenities selects listing with most amenities."""
		result: dict[str, ListingWithCost | None] = rank_by_category([lwc_a, lwc_b])
		# lwc_b has 5 amenities > lwc_a 3
		assert result["best_amenities"] is lwc_b

	def test_best_reviews(
		self,
		lwc_a: ListingWithCost,
		lwc_c: ListingWithCost,
	) -> None:
		"""Best reviews uses composite score (60% rating + 40% volume)."""
		result: dict[str, ListingWithCost | None] = rank_by_category([lwc_a, lwc_c])
		# lwc_a: 0.6*(4.91/5)+0.4*(126/126) = 0.989
		# lwc_c: 0.6*(4.95/5)+0.4*(86/126)  = 0.867
		# lwc_a wins on composite score due to many more reviews
		assert result["best_reviews"] is lwc_a

	def test_best_location(
		self,
		lwc_a: ListingWithCost,
	) -> None:
		"""Best location selects listing with neighbourhood set."""
		# Create a listing without neighbourhood
		no_location = ListingWithCost(
			listing=AirbnbListing(
				url="https://www.airbnb.com/rooms/111",
				title="No Location",
			),
			cost_breakdown=CostBreakdown(
				total_cost=100.0,
				num_people=1,
				num_nights=1,
				cost_per_person=100.0,
				cost_per_night=100.0,
				cost_per_night_per_person=100.0,
			),
		)
		result: dict[str, ListingWithCost | None] = rank_by_category(
			[no_location, lwc_a]
		)
		assert result["best_location"] is lwc_a

	def test_returns_one_per_category(
		self,
		lwc_a: ListingWithCost,
		lwc_b: ListingWithCost,
		lwc_c: ListingWithCost,
	) -> None:
		"""Each category returns exactly one listing (or None)."""
		result: dict[str, ListingWithCost | None] = rank_by_category(
			[lwc_a, lwc_b, lwc_c]
		)
		expected_keys: set[str] = {
			"best_price",
			"best_value",
			"best_amenities",
			"best_location",
			"best_reviews",
		}
		assert set(result.keys()) == expected_keys
		for value in result.values():
			assert value is None or isinstance(value, ListingWithCost)


class TestCalculateTripTotals:
	"""Verify multi-week per-person cost aggregation."""

	def test_variable_participants(
		self,
		lwc_a: ListingWithCost,
		lwc_b: ListingWithCost,
	) -> None:
		"""Costs are split per-week based on who's present."""
		week1 = WeekAnalysis(
			week=TripWeek(
				week_label="Week 1",
				check_in=date(2026, 4, 24),
				check_out=date(2026, 5, 2),
				location="Mexico City",
				participants=["Karina", "Luis", "Mom"],
				num_people=3,
				min_bedrooms=2,
				min_bathrooms=1,
			),
			matched_listings=[lwc_a],
			best_price=lwc_a,
		)
		week2 = WeekAnalysis(
			week=TripWeek(
				week_label="Week 2",
				check_in=date(2026, 5, 2),
				check_out=date(2026, 5, 9),
				location="Mexico City",
				participants=["Karina", "Luis", "Mom", "Laura"],
				num_people=4,
				min_bedrooms=3,
				min_bathrooms=2,
			),
			matched_listings=[lwc_b],
			best_price=lwc_b,
		)

		totals: dict[str, int | float] = calculate_trip_totals(
			[week1, week2],
			["Karina", "Luis", "Mom", "Laura"],
		)

		# Karina, Luis, Mom: present both weeks
		# Week1 cost_per_person = 385.67, Week2 cost_per_person = 345.62
		assert totals["Karina"] == round(385.67 + 345.62, 2)
		assert totals["Luis"] == round(385.67 + 345.62, 2)
		assert totals["Mom"] == round(385.67 + 345.62, 2)
		# Laura: only present week 2
		assert totals["Laura"] == 345.62

	def test_participant_not_in_any_week(
		self,
		lwc_a: ListingWithCost,
	) -> None:
		"""Participants not in any week get 0.0 total."""
		week1 = WeekAnalysis(
			week=TripWeek(
				week_label="Week 1",
				check_in=date(2026, 4, 24),
				check_out=date(2026, 5, 2),
				location="Mexico City",
				participants=["Karina"],
				num_people=1,
				min_bedrooms=1,
				min_bathrooms=1,
			),
			matched_listings=[lwc_a],
			best_price=lwc_a,
		)
		totals: dict[str, int | float] = calculate_trip_totals(
			[week1], ["Karina", "Ghost"]
		)
		assert totals["Karina"] == 385.67
		assert totals["Ghost"] == 0.0

	def test_no_best_price_skips_week(
		self,
	) -> None:
		"""Weeks without a best_price pick contribute nothing."""
		week1 = WeekAnalysis(
			week=TripWeek(
				week_label="Week 1",
				check_in=date(2026, 4, 24),
				check_out=date(2026, 5, 2),
				location="Mexico City",
				participants=["Karina"],
				num_people=1,
				min_bedrooms=1,
				min_bathrooms=1,
			),
			matched_listings=[],
			best_price=None,
		)
		totals: dict[str, int | float] = calculate_trip_totals([week1], ["Karina"])
		assert totals["Karina"] == 0.0

	def test_empty_week_analyses(self) -> None:
		"""Empty analyses returns all zeros."""
		totals: dict[str, int | float] = calculate_trip_totals([], ["Karina", "Luis"])
		assert totals == {"Karina": 0.0, "Luis": 0.0}


# ══════════════════════════════════════════════════════════════
# parse_booking_price — num_people parameter
# ══════════════════════════════════════════════════════════════


class TestParseBookingPriceNumPeople:
	"""Verify num_people parameter in parse_booking_price."""

	def test_default_num_people_is_one(self) -> None:
		"""Without num_people, cost_per_person equals total_cost."""
		html = "<html><body><div>$700 for 7 nights</div></body></html>"
		breakdown: CostBreakdown = parse_booking_price(page_html=html)
		assert breakdown.num_people == 1
		assert breakdown.cost_per_person == 700.0

	def test_num_people_splits_cost(self) -> None:
		"""num_people=2 halves the per-person cost."""
		html = "<html><body><div>$700 for 7 nights</div></body></html>"
		breakdown: CostBreakdown = parse_booking_price(page_html=html, num_people=2)
		assert breakdown.num_people == 2
		assert breakdown.cost_per_person == 350.0
		assert breakdown.cost_per_night_per_person == 50.0

	def test_num_people_four(self) -> None:
		"""num_people=4 splits cost four ways."""
		html = """
		<html><body>
		<div>$200.00 x 5 nights</div>
		<div>Total (USD) $1,000.00</div>
		</body></html>
		"""
		breakdown: CostBreakdown = parse_booking_price(page_html=html, num_people=4)
		assert breakdown.num_people == 4
		assert breakdown.cost_per_person == 250.0
		assert breakdown.cost_per_night == 200.0
		assert breakdown.cost_per_night_per_person == 50.0

	def test_num_people_zero_raises(self) -> None:
		"""num_people=0 raises ValueError."""
		html = "<html><body><div>$700 for 7 nights</div></body></html>"
		with pytest.raises(ValueError, match="num_people must be at least 1"):
			parse_booking_price(page_html=html, num_people=0)

	def test_num_people_negative_raises(self) -> None:
		"""Negative num_people raises ValueError."""
		html = "<html><body><div>$700 for 7 nights</div></body></html>"
		with pytest.raises(ValueError, match="num_people must be at least 1"):
			parse_booking_price(page_html=html, num_people=-1)


# ══════════════════════════════════════════════════════════════
# parse_listing_details — neighbourhood from og:title
# ══════════════════════════════════════════════════════════════


class TestParseListingDetailsNeighborhood:
	"""Verify neighbourhood extraction — H1 title, og:title, meta description."""

	def test_h1_extracts_specific_neighborhood(self) -> None:
		"""H1 'Remodelled Apartment in Central Condesa, CDMX' yields Condesa (normalised)."""
		html = """
		<html><head>
		<meta property="og:title" content="Rental unit in Mexico City · ★4.96 · 2 bedrooms · 2 beds · 2 baths" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Remodelled Apartment in Central Condesa, CDMX</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Condesa"

	def test_h1_extracts_hyphenated_neighborhood(self) -> None:
		"""H1 'Apartment in Roma-Condesa ...' yields Roma Norte (normalised via CDMX map)."""
		html = """
		<html><head>
		<meta property="og:title" content="Rental unit in Mexico City · ★5.0 · 2 bedrooms · 2 beds · 1 bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Apartment in Roma-Condesa, very conveniently located.</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Roma Norte"

	def test_h1_rejects_generic_description(self) -> None:
		"""H1 with 'in a picturesque neighborhood' falls back to og:title city."""
		html = """
		<html><head>
		<meta property="og:title" content="Home in Mexico City · ★4.97 · 2 bedrooms · 2 beds · 1 bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Well-equipped house in a picturesque and safe neighborhood</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Mexico City"

	def test_h1_rejects_the_center(self) -> None:
		"""H1 with 'in the center of the city' falls back to og:title city."""
		html = """
		<html><head>
		<meta property="og:title" content="Rental unit in Mexico City · ★5.0 · 2 bedrooms · 2 beds · 2 baths" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Great apartment in the center of the city.</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Mexico City"

	def test_og_title_extracts_city(self) -> None:
		"""og:title 'Rental unit in Mexico City · ...' yields Mexico City."""
		html = """
		<html><head>
		<meta property="og:title" content="Rental unit in Mexico City · ★5.0 · 2 bedrooms · 2 beds · 2 baths" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body></body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Mexico City"

	def test_og_title_extracts_neighborhood_with_spaces(self) -> None:
		"""og:title 'Home in Roma Norte · ...' yields Roma Norte."""
		html = """
		<html><head>
		<meta property="og:title" content="Home in Roma Norte · ★4.88 · 1 bedroom · 1 bed · 1 bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body></body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Roma Norte"

	def test_fallback_to_meta_description(self) -> None:
		"""When og:title has no 'in <Location>', fall back to meta description (normalised)."""
		html = """
		<html><head>
		<meta property="og:title" content="Amazing Apartment · ★4.5 · 2 bedrooms" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		<meta name="description" content="Cozy apartment in Condesa, Mexico City" />
		</head><body></body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Condesa"

	def test_no_neighborhood_available(self) -> None:
		"""When neither og:title nor meta desc has location, neighborhood is None."""
		html = """
		<html><head>
		<meta property="og:title" content="Amazing Apartment · ★4.5" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body></body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood is None

	def test_h1_keyword_scan_finds_neighborhood_in_title(self) -> None:
		"""H1 without 'in' pattern uses keyword scan to find known neighbourhood."""
		html = """
		<html><head>
		<meta property="og:title" content="Home in Mexico City · ★4.88 · 1 bedroom · 1 bed · 1 private bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>CASA CONDESA ZAPATA *****</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Condesa"

	def test_h1_no_known_name_falls_back_to_og_title(self) -> None:
		"""H1 with no known neighbourhood names falls back to og:title city."""
		html = """
		<html><head>
		<meta property="og:title" content="Home in Mexico City · ★4.88 · 1 bedroom · 1 bed · 1 private bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Beautiful new loft, very central</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Mexico City"

	def test_h1_at_preposition_extracts_neighborhood(self) -> None:
		"""H1 with 'at La Roma' extracts Roma Norte via keyword scan."""
		html = """
		<html><head>
		<meta property="og:title" content="Rental unit in Mexico City · ★4.5 · 1 bedroom · 1 bed · 1 bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Cozy flat w/great views at La Roma</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Roma Norte"

	def test_h1_near_preposition_extracts_neighborhood(self) -> None:
		"""H1 with 'near the Angel of Independence' extracts Colonia Juárez."""
		html = """
		<html><head>
		<meta property="og:title" content="Home in Mexico City · ★4.3 · 2 bedrooms · 2 beds · 1 bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Magnificent apartment near the Angel of Independence</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Colonia Juárez"

	def test_h1_in_the_historic_center_extracts_neighborhood(self) -> None:
		"""H1 with 'in the Historic Center of Mexico City' extracts Centro Histórico."""
		html = """
		<html><head>
		<meta property="og:title" content="Home in Mexico City · ★4.9 · 1 bedroom · 1 bed · 1 bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Magnificent apartment in the Historic Center of Mexico City</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Centro Histórico"

	def test_keyword_scan_in_title_without_preposition(self) -> None:
		"""H1 like 'Beautiful, Cozy, Heart Condesa' finds Condesa via keyword scan."""
		html = """
		<html><head>
		<meta property="og:title" content="Home in Mexico City · ★4.5 · 1 bedroom · 1 bed · 1 bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<h1>Beautiful, Cozy, Lovely, Very SAFE, Heart Condesa</h1>
		</body></html>
		"""
		listing: AirbnbListing = parse_listing_details(
			location="Mexico City", page_html=html
		)
		assert listing.neighborhood == "Condesa"


# ══════════════════════════════════════════════════════════════
# _normalize_neighborhood / _scan_for_known_neighborhoods
# ══════════════════════════════════════════════════════════════


class TestNormalizeNeighborhood:
	"""Verify neighbourhood normalisation via the CDMX mapping."""

	def test_exact_match_returns_canonical(self) -> None:
		"""Known abbreviation 'Roma Nte' maps to 'Roma Norte'."""
		assert (
			_normalize_neighborhood("Roma Nte", location="Mexico City") == "Roma Norte"
		)

	def test_case_insensitive_match(self) -> None:
		"""Lookup is case-insensitive: 'roma nte' maps to 'Roma Norte'."""
		assert (
			_normalize_neighborhood("roma nte", location="Mexico City") == "Roma Norte"
		)

	def test_suffix_trimming_cdmx(self) -> None:
		"""Strips ', CDMX' suffix before looking up: 'Condesa, CDMX' → 'Condesa'."""
		assert (
			_normalize_neighborhood("Condesa, CDMX", location="Mexico City")
			== "Condesa"
		)

	def test_suffix_trimming_mexico_city(self) -> None:
		"""Strips ', Mexico City' suffix: 'Historic Center, Mexico City' → 'Centro Histórico'."""
		assert (
			_normalize_neighborhood(
				"Historic Center, Mexico City", location="Mexico City"
			)
			== "Centro Histórico"
		)

	def test_suffix_trimming_of_mexico_city(self) -> None:
		"""Strips ' of Mexico City' suffix: 'Historic Center of Mexico City' → 'Centro Histórico'."""
		assert (
			_normalize_neighborhood(
				"Historic Center of Mexico City", location="Mexico City"
			)
			== "Centro Histórico"
		)

	def test_unknown_passes_through(self) -> None:
		"""Unknown neighbourhood names pass through unchanged."""
		assert _normalize_neighborhood("Polanco", location="Mexico City") == "Polanco"

	def test_whitespace_stripped(self) -> None:
		"""Leading/trailing whitespace is stripped before lookup."""
		assert (
			_normalize_neighborhood("  Roma Norte  ", location="Mexico City")
			== "Roma Norte"
		)


class TestScanForKnownNeighborhoods:
	"""Verify keyword scanning for known CDMX neighbourhood names."""

	def test_finds_neighborhood_in_text(self) -> None:
		"""Finds 'Condesa' in free text and returns canonical name."""
		result = _scan_for_known_neighborhoods(
			"Beautiful, Cozy, Heart Condesa", location="Mexico City"
		)
		assert result == "Condesa"

	def test_longest_match_wins(self) -> None:
		"""Prefers 'Historic Center' (longer) over 'Centro' when both could match."""
		result = _scan_for_known_neighborhoods(
			"Apartment in the Historic Center", location="Mexico City"
		)
		assert result == "Centro Histórico"

	def test_case_insensitive_scan(self) -> None:
		"""Keyword scan is case-insensitive: 'CONDESA' matches 'Condesa' key."""
		result = _scan_for_known_neighborhoods(
			"CASA CONDESA ZAPATA", location="Mexico City"
		)
		assert result == "Condesa"

	def test_no_match_returns_none(self) -> None:
		"""Returns None when no known neighbourhood name is found."""
		result = _scan_for_known_neighborhoods(
			"Beautiful new loft, very central", location="Mexico City"
		)
		assert result is None

	def test_finds_tabacalera_with_revolution(self) -> None:
		"""Finds 'Tabacalera' in 'Sennse Tabacalera - Monument to the Revolution'."""
		result = _scan_for_known_neighborhoods(
			"Sennse Tabacalera - Monument to the Revolution",
			location="Mexico City",
		)
		assert result == "Colonia Tabacalera"

	def test_finds_reforma(self) -> None:
		"""Finds 'Reforma' in listing title text."""
		result = _scan_for_known_neighborhoods(
			"Boutique Loft · Reforma frente a Reforma 222",
			location="Mexico City",
		)
		assert result == "Colonia Cuauhtémoc"


# ══════════════════════════════════════════════════════════════
# parse_listing_page — combined tool
# ══════════════════════════════════════════════════════════════


class TestParseListingPage:
	"""Verify the combined parse_listing_page tool."""

	def test_returns_listing_with_cost(self) -> None:
		"""parse_listing_page returns a ListingWithCost with both fields."""
		html = """
		<html><head>
		<meta property="og:title" content="Rental unit in Mexico City · ★5.0 · 2 bedrooms · 2 beds · 2 baths" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/123456" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123456" />
		</head><body>
		<div>$344 for 7 nights</div>
		</body></html>
		"""
		result: ListingWithCost = parse_listing_page(
			location="Mexico City", page_html=html, num_people=2
		)
		assert isinstance(result, ListingWithCost)
		assert isinstance(result.listing, AirbnbListing)
		assert isinstance(result.cost_breakdown, CostBreakdown)

	def test_listing_details_populated(self) -> None:
		"""Listing details are correctly extracted."""
		html = """
		<html><head>
		<meta property="og:title" content="Home in Roma Norte · ★4.88 · 1 bedroom · 1 bed · 1 bath" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/999" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/999" />
		</head><body>
		<div>$500 for 5 nights</div>
		</body></html>
		"""
		result: ListingWithCost = parse_listing_page(
			location="Mexico City", page_html=html
		)
		assert result.listing.num_bedrooms == 1
		assert result.listing.num_beds == 1
		assert result.listing.num_bathrooms == 1
		assert result.listing.neighborhood == "Roma Norte"

	def test_cost_breakdown_populated(self) -> None:
		"""Cost breakdown is correctly computed with num_people."""
		html = """
		<html><head>
		<meta property="og:title" content="Rental unit in Condesa · ★4.9 · 3 bedrooms · 3 beds · 2 baths" />
		<meta property="og:url" content="https://www.airbnb.com/rooms/555" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/555" />
		</head><body>
		<div>$100.00 x 7 nights</div>
		<div>Cleaning fee $50.00</div>
		<div>Total (USD) $750.00</div>
		</body></html>
		"""
		result: ListingWithCost = parse_listing_page(
			location="Mexico City", page_html=html, num_people=3
		)
		assert result.cost_breakdown.total_cost == 750.0
		assert result.cost_breakdown.num_people == 3
		assert result.cost_breakdown.cost_per_person == 250.0
		assert result.cost_breakdown.num_nights == 7
		assert result.cost_breakdown.fees.get("cleaning_fee") == 50.0

	def test_raises_on_missing_url(self) -> None:
		"""Raises ValueError when no listing URL in the page."""
		html = """
		<html><head></head><body>
		<div>$344 for 7 nights</div>
		</body></html>
		"""
		with pytest.raises(ValueError, match="Could not determine listing URL"):
			parse_listing_page(location="Mexico City", page_html=html)

	def test_raises_on_missing_price(self) -> None:
		"""Raises ModelRetry when no price can be extracted."""
		html = """
		<html><head>
		<meta property="og:url" content="https://www.airbnb.com/rooms/123" />
		<link rel="canonical" href="https://www.airbnb.com/rooms/123" />
		</head><body>No price here</body></html>
		"""
		with pytest.raises(ModelRetry, match="Could not extract total price"):
			parse_listing_page(location="Mexico City", page_html=html)
