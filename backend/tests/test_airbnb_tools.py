"""Tests for Airbnb domain tools — URLs, parsers, and analysis functions."""

from datetime import date
from pathlib import Path

import pytest

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
	parse_booking_price,
	parse_listing_details,
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
			num_adults=4,
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
			num_adults=2,
		)
		assert "Ju%C3%A1rez%2C%20Mexico%20City" in url

	def test_invalid_num_adults_raises(self) -> None:
		"""Zero or negative adults raises ValueError."""
		with pytest.raises(ValueError, match="num_adults must be at least 1"):
			build_search_url("CDMX", "2026-05-02", "2026-05-09", 0)

		with pytest.raises(ValueError, match="num_adults must be at least 1"):
			build_search_url("CDMX", "2026-05-02", "2026-05-09", -1)


class TestBuildListingUrl:
	"""Verify Airbnb listing URL construction."""

	def test_basic_url_format(self) -> None:
		"""URL follows the documented Airbnb listing format."""
		url: str = build_listing_url(
			room_id="863180984181188292",
			check_in="2026-05-02",
			check_out="2026-05-09",
			num_adults=4,
		)
		assert url.startswith("https://www.airbnb.com/rooms/863180984181188292")
		assert "adults=4" in url
		assert "check_in=2026-05-02" in url
		assert "check_out=2026-05-09" in url

	def test_invalid_num_adults_raises(self) -> None:
		"""Zero or negative adults raises ValueError."""
		with pytest.raises(ValueError, match="num_adults must be at least 1"):
			build_listing_url("12345", "2026-05-02", "2026-05-09", 0)


# ══════════════════════════════════════════════════════════════
# Parser Tests
# ══════════════════════════════════════════════════════════════


class TestParseSearchResults:
	"""Verify search results HTML parsing."""

	def test_returns_list(self) -> None:
		"""Parser always returns a list (may be empty for SPA pages)."""
		result: list[AirbnbListing] = parse_search_results(
			"<html><body>No listings</body></html>"
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
		listings: list[AirbnbListing] = parse_search_results(html)
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
		listings: list[AirbnbListing] = parse_search_results(html)
		assert len(listings) == 1

	def test_search_page_fixture(self) -> None:
		"""Parser runs without error on the saved search page fixture."""
		if not SEARCH_PAGE_HTML.exists():
			pytest.skip("Search page HTML fixture not found")
		html: str = SEARCH_PAGE_HTML.read_text(encoding="utf-8")
		listings: list[AirbnbListing] = parse_search_results(html)
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
		listings: list[AirbnbListing] = parse_search_results(html)
		assert len(listings) == 1
		assert listings[0].nightly_rate == 220.0


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
		listing: AirbnbListing = parse_listing_details(html)
		assert listing.url == "https://www.airbnb.com/rooms/12345"
		assert listing.title == "Beautiful Loft in Roma Norte"
		assert listing.num_bedrooms == 3
		assert listing.num_bathrooms == 2

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
		listing: AirbnbListing = parse_listing_details(html)
		assert listing.rating == 4.91
		assert listing.num_reviews == 126

	def test_raises_on_missing_url(self) -> None:
		"""Parser raises ValueError if no URL can be found."""
		with pytest.raises(ValueError, match="Could not determine listing URL"):
			parse_listing_details("<html><body>No URL</body></html>")

	def test_listing_page_fixture(self) -> None:
		"""Parser runs without error on the saved listing page fixture."""
		if not LISTING_PAGE_HTML.exists():
			pytest.skip("Listing page HTML fixture not found")
		html: str = LISTING_PAGE_HTML.read_text(encoding="utf-8")
		listing: AirbnbListing = parse_listing_details(html)
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
		breakdown: CostBreakdown = parse_booking_price(html)
		assert breakdown.total_cost == 1542.66
		assert breakdown.num_nights == 7
		assert breakdown.fees.get("cleaning_fee") == 50.0
		assert breakdown.fees.get("service_fee") == 120.0

	def test_raises_on_missing_price(self) -> None:
		"""Parser raises ValueError when no price is found."""
		with pytest.raises(ValueError, match="Could not extract total price"):
			parse_booking_price("<html><body>No price</body></html>")

	def test_fallback_to_computed_total(self) -> None:
		"""When no explicit total, compute from nightly rate + fees."""
		html = """
		<html><body>
		<div>$200.00 x 3 nights</div>
		<div>Cleaning fee $50.00</div>
		</body></html>
		"""
		breakdown: CostBreakdown = parse_booking_price(html)
		# 200 * 3 + 50 = 650
		assert breakdown.total_cost == 650.0
		assert breakdown.num_nights == 3


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
		"""Best reviews selects highest rating, reviews as tiebreaker."""
		result: dict[str, ListingWithCost | None] = rank_by_category([lwc_a, lwc_c])
		# lwc_c has 4.95 > lwc_a 4.91
		assert result["best_reviews"] is lwc_c

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
