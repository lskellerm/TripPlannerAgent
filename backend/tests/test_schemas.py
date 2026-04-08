"""Tests for Pydantic data models (TripWeek, AirbnbListing, CostBreakdown, etc.)."""

from datetime import date

import pytest
from pydantic import ValidationError

from src.agent.schemas import TripWeek
from src.airbnb.schemas import (
	AirbnbListing,
	CostBreakdown,
	ListingWithCost,
	TripAnalysis,
	WeekAnalysis,
)

# ── Fixtures ──


@pytest.fixture
def sample_trip_week() -> TripWeek:
	"""Return a fully populated TripWeek instance."""
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
		required_amenities=["Wi-Fi", "AC"],
		max_price_per_person=570.66,
	)


@pytest.fixture
def sample_listing() -> AirbnbListing:
	"""Return a fully populated AirbnbListing instance."""
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
		image_url="https://example.com/image.jpg",
	)


@pytest.fixture
def sample_cost_breakdown() -> CostBreakdown:
	"""Return a CostBreakdown matching CDMX trip listing data."""
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
def sample_listing_with_cost(
	sample_listing: AirbnbListing,
	sample_cost_breakdown: CostBreakdown,
) -> ListingWithCost:
	"""Return a ListingWithCost combining listing and cost data."""
	return ListingWithCost(
		listing=sample_listing,
		cost_breakdown=sample_cost_breakdown,
	)


# ── TripWeek Tests ──


class TestTripWeek:
	"""Verify TripWeek model creation, defaults, and immutability."""

	def test_full_construction(self, sample_trip_week: TripWeek) -> None:
		"""TripWeek with all fields set is valid."""
		assert sample_trip_week.week_label == "Week 1"
		assert sample_trip_week.check_in == date(2026, 4, 24)
		assert sample_trip_week.check_out == date(2026, 5, 2)
		assert sample_trip_week.location == "Mexico City"
		assert sample_trip_week.neighborhood_constraints == ["Roma Norte"]
		assert sample_trip_week.participants == ["Karina", "Luis", "Mom"]
		assert sample_trip_week.num_people == 3
		assert sample_trip_week.min_bedrooms == 2
		assert sample_trip_week.min_bathrooms == 1
		assert sample_trip_week.min_rating == 4.5
		assert sample_trip_week.required_amenities == ["Wi-Fi", "AC"]
		assert sample_trip_week.max_price_per_person == 570.66

	def test_defaults(self) -> None:
		"""TripWeek optional fields default correctly."""
		week = TripWeek(
			week_label="Week 2",
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			participants=["Karina", "Luis", "Mom", "Laura"],
			num_people=4,
			min_bedrooms=3,
			min_bathrooms=2,
		)
		assert week.neighborhood_constraints == []
		assert week.min_rating == 0.0
		assert week.required_amenities == []
		assert week.max_price_per_person is None

	def test_minimal_construction(self) -> None:
		"""TripWeek with only essential fields infers sensible defaults."""
		week = TripWeek(
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="Mexico City",
			num_people=2,
		)
		assert week.week_label == "Week 1"
		assert week.participants == []
		assert week.min_bedrooms == 1  # ceil(2/2)
		assert week.min_bathrooms == 1
		assert week.min_rating == 0.0
		assert week.required_amenities == []
		assert week.neighborhood_constraints == []
		assert week.max_price_per_person is None

	def test_infer_min_bedrooms_from_num_people(self) -> None:
		"""min_bedrooms is inferred as ceil(num_people / 2) when omitted."""
		# 1 person → 1 bedroom
		week1 = TripWeek(
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="CDMX",
			num_people=1,
		)
		assert week1.min_bedrooms == 1

		# 3 people → 2 bedrooms
		week3 = TripWeek(
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="CDMX",
			num_people=3,
		)
		assert week3.min_bedrooms == 2

		# 4 people → 2 bedrooms
		week4 = TripWeek(
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="CDMX",
			num_people=4,
		)
		assert week4.min_bedrooms == 2

		# 5 people → 3 bedrooms
		week5 = TripWeek(
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="CDMX",
			num_people=5,
		)
		assert week5.min_bedrooms == 3

	def test_explicit_min_bedrooms_not_overridden(self) -> None:
		"""Explicitly passed min_bedrooms is not overridden by inference."""
		week = TripWeek(
			check_in=date(2026, 5, 2),
			check_out=date(2026, 5, 9),
			location="CDMX",
			num_people=4,
			min_bedrooms=1,  # Explicit: 1, inferred would be 2
		)
		assert week.min_bedrooms == 1

	def test_frozen_immutability(self, sample_trip_week: TripWeek) -> None:
		"""TripWeek is frozen and rejects attribute assignment."""
		with pytest.raises(ValidationError):
			sample_trip_week.week_label = "Modified"

	def test_serialization_roundtrip(self, sample_trip_week: TripWeek) -> None:
		"""TripWeek model_dump → TripWeek roundtrip preserves data."""
		data = sample_trip_week.model_dump()
		restored = TripWeek(**data)
		assert restored == sample_trip_week

	def test_json_roundtrip(self, sample_trip_week: TripWeek) -> None:
		"""TripWeek model_dump_json → model_validate_json roundtrip."""
		json_str = sample_trip_week.model_dump_json()
		restored = TripWeek.model_validate_json(json_str)
		assert restored == sample_trip_week

	def test_missing_required_fields(self) -> None:
		"""TripWeek raises ValidationError when required fields are missing."""
		with pytest.raises(ValidationError):
			TripWeek(  # type: ignore[call-arg]  # ty: ignore[missing-argument]
				week_label="Week 1",
				check_in=date(2026, 4, 24),
				# Missing: check_out, location, num_people
			)


# ── AirbnbListing Tests ──


class TestAirbnbListing:
	"""Verify AirbnbListing model creation, defaults, and immutability."""

	def test_full_construction(self, sample_listing: AirbnbListing) -> None:
		"""AirbnbListing with all fields set is valid."""
		assert sample_listing.url == "https://www.airbnb.com/rooms/863180984181188292"
		assert "Steps from Reforma" in sample_listing.title
		assert sample_listing.total_cost == 1542.66
		assert sample_listing.num_bedrooms == 3
		assert sample_listing.num_bathrooms == 3
		assert sample_listing.rating == 4.91
		assert sample_listing.num_reviews == 126

	def test_minimal_construction(self) -> None:
		"""AirbnbListing with only required fields (url, title) is valid."""
		listing = AirbnbListing(
			url="https://www.airbnb.com/rooms/12345",
			title="Minimal Listing",
		)
		assert listing.total_cost is None
		assert listing.nightly_rate is None
		assert listing.num_beds is None
		assert listing.num_bedrooms is None
		assert listing.num_bathrooms is None
		assert listing.amenities == []
		assert listing.neighborhood is None
		assert listing.rating is None
		assert listing.num_reviews is None
		assert listing.image_url is None

	def test_frozen_immutability(self, sample_listing: AirbnbListing) -> None:
		"""AirbnbListing is frozen and rejects attribute assignment."""
		with pytest.raises(ValidationError):
			sample_listing.title = "Modified"

	def test_serialization_roundtrip(self, sample_listing: AirbnbListing) -> None:
		"""AirbnbListing model_dump → AirbnbListing roundtrip preserves data."""
		data = sample_listing.model_dump()
		restored = AirbnbListing(**data)
		assert restored == sample_listing

	def test_json_roundtrip(self, sample_listing: AirbnbListing) -> None:
		"""AirbnbListing model_dump_json → model_validate_json roundtrip."""
		json_str = sample_listing.model_dump_json()
		restored = AirbnbListing.model_validate_json(json_str)
		assert restored == sample_listing


# ── CostBreakdown Tests ──


class TestCostBreakdown:
	"""Verify CostBreakdown model creation and immutability."""

	def test_full_construction(self, sample_cost_breakdown: CostBreakdown) -> None:
		"""CostBreakdown with all fields set is valid."""
		assert sample_cost_breakdown.total_cost == 1542.66
		assert sample_cost_breakdown.num_people == 4
		assert sample_cost_breakdown.num_nights == 7
		assert sample_cost_breakdown.cost_per_person == 385.67
		assert sample_cost_breakdown.cost_per_night == 220.38
		assert sample_cost_breakdown.cost_per_night_per_person == 55.10
		assert sample_cost_breakdown.fees == {
			"cleaning_fee": 50.0,
			"service_fee": 120.0,
		}

	def test_empty_fees_default(self) -> None:
		"""CostBreakdown.fees defaults to empty dict."""
		breakdown = CostBreakdown(
			total_cost=1000.0,
			num_people=2,
			num_nights=5,
			cost_per_person=500.0,
			cost_per_night=200.0,
			cost_per_night_per_person=100.0,
		)
		assert breakdown.fees == {}

	def test_frozen_immutability(self, sample_cost_breakdown: CostBreakdown) -> None:
		"""CostBreakdown is frozen and rejects attribute assignment."""
		with pytest.raises(ValidationError):
			sample_cost_breakdown.total_cost = 0.0

	def test_serialization_roundtrip(
		self, sample_cost_breakdown: CostBreakdown
	) -> None:
		"""CostBreakdown model_dump → CostBreakdown roundtrip preserves data."""
		data = sample_cost_breakdown.model_dump()
		restored = CostBreakdown(**data)
		assert restored == sample_cost_breakdown


# ── ListingWithCost Tests ──


class TestListingWithCost:
	"""Verify ListingWithCost composite model."""

	def test_construction(self, sample_listing_with_cost: ListingWithCost) -> None:
		"""ListingWithCost nests listing and cost_breakdown correctly."""
		assert sample_listing_with_cost.listing.title.startswith("Steps from Reforma")
		assert sample_listing_with_cost.cost_breakdown.cost_per_person == 385.67

	def test_frozen_immutability(
		self, sample_listing_with_cost: ListingWithCost
	) -> None:
		"""ListingWithCost is frozen and rejects attribute assignment."""
		with pytest.raises(ValidationError):
			sample_listing_with_cost.listing = None  # ty: ignore[invalid-assignment]

	def test_serialization_roundtrip(
		self, sample_listing_with_cost: ListingWithCost
	) -> None:
		"""ListingWithCost model_dump → ListingWithCost roundtrip preserves data."""
		data = sample_listing_with_cost.model_dump()
		restored = ListingWithCost(**data)
		assert restored == sample_listing_with_cost


# ── WeekAnalysis Tests ──


class TestWeekAnalysis:
	"""Verify WeekAnalysis model with categorical best picks."""

	def test_minimal_construction(self, sample_trip_week: TripWeek) -> None:
		"""WeekAnalysis with no matched listings is valid."""
		analysis = WeekAnalysis(week=sample_trip_week)
		assert analysis.week == sample_trip_week
		assert analysis.matched_listings == []
		assert analysis.best_price is None
		assert analysis.best_value is None
		assert analysis.best_amenities is None
		assert analysis.best_location is None
		assert analysis.best_reviews is None

	def test_full_construction(
		self,
		sample_trip_week: TripWeek,
		sample_listing_with_cost: ListingWithCost,
	) -> None:
		"""WeekAnalysis with matched listings and best picks is valid."""
		analysis = WeekAnalysis(
			week=sample_trip_week,
			matched_listings=[sample_listing_with_cost],
			best_price=sample_listing_with_cost,
			best_value=sample_listing_with_cost,
			best_amenities=sample_listing_with_cost,
			best_location=sample_listing_with_cost,
			best_reviews=sample_listing_with_cost,
		)
		assert len(analysis.matched_listings) == 1
		assert analysis.best_price is not None
		assert analysis.best_reviews is not None

	def test_frozen_immutability(self, sample_trip_week: TripWeek) -> None:
		"""WeekAnalysis is frozen and rejects attribute assignment."""
		analysis = WeekAnalysis(week=sample_trip_week)
		with pytest.raises(ValidationError):
			analysis.best_price = None

	def test_serialization_roundtrip(
		self,
		sample_trip_week: TripWeek,
		sample_listing_with_cost: ListingWithCost,
	) -> None:
		"""WeekAnalysis model_dump → WeekAnalysis roundtrip preserves data."""
		analysis = WeekAnalysis(
			week=sample_trip_week,
			matched_listings=[sample_listing_with_cost],
			best_price=sample_listing_with_cost,
		)
		data = analysis.model_dump()
		restored = WeekAnalysis(**data)
		assert restored == analysis


# ── TripAnalysis Tests ──


class TestTripAnalysis:
	"""Verify TripAnalysis aggregation model."""

	def test_construction(
		self,
		sample_trip_week: TripWeek,
		sample_listing_with_cost: ListingWithCost,
	) -> None:
		"""TripAnalysis with weeks and per-person totals is valid."""
		week_analysis = WeekAnalysis(
			week=sample_trip_week,
			matched_listings=[sample_listing_with_cost],
			best_price=sample_listing_with_cost,
		)
		trip = TripAnalysis(
			weeks=[week_analysis],
			per_person_totals={"Karina": 385.67, "Luis": 385.67, "Mom": 385.67},
			overall_summary="3-week CDMX trip analysis complete.",
		)
		assert len(trip.weeks) == 1
		assert trip.per_person_totals["Luis"] == 385.67
		assert "CDMX" in trip.overall_summary

	def test_frozen_immutability(self, sample_trip_week: TripWeek) -> None:
		"""TripAnalysis is frozen and rejects attribute assignment."""
		trip = TripAnalysis(
			weeks=[WeekAnalysis(week=sample_trip_week)],
			per_person_totals={},
			overall_summary="Test",
		)
		with pytest.raises(ValidationError):
			trip.overall_summary = "Changed"

	def test_json_roundtrip(
		self,
		sample_trip_week: TripWeek,
		sample_listing_with_cost: ListingWithCost,
	) -> None:
		"""TripAnalysis model_dump_json → model_validate_json roundtrip."""
		week_analysis = WeekAnalysis(
			week=sample_trip_week,
			matched_listings=[sample_listing_with_cost],
		)
		trip = TripAnalysis(
			weeks=[week_analysis],
			per_person_totals={"Karina": 385.67, "Luis": 385.67},
			overall_summary="Trip summary.",
		)
		json_str = trip.model_dump_json()
		restored = TripAnalysis.model_validate_json(json_str)
		assert restored == trip
