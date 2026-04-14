"""Airbnb-specific Pydantic models.

Defines domain models for Airbnb listing metadata, cost breakdowns,
per-listing cost analysis, per-week analysis with categorical rankings,
and full multi-week trip analysis summaries.
"""

from typing import Union

from pydantic import BaseModel, ConfigDict, Field

from src.agent.schemas import TripWeek


class AirbnbListing(BaseModel):
	"""Airbnb listing metadata extracted from search results or detail pages.

	Fields that may not be available from the search results page
	(e.g., ``total_cost``, ``num_bedrooms``) are optional with ``None``
	defaults.  They are populated when the agent navigates to the
	individual listing detail page.

	Attributes:
		url: Full URL of the Airbnb listing.
		title: Listing title from Airbnb.
		total_cost: Total booking cost including all fees (available after
			clicking Reserve on the listing page).
		nightly_rate: Per-night rate before fees.
		num_beds: Number of beds in the listing.
		num_bedrooms: Number of bedrooms.
		num_bathrooms: Number of bathrooms.
		amenities: List of amenities (e.g., "Wi-Fi", "AC", "washer/dryer").
		neighborhood: Neighborhood or area name.
		rating: Guest rating on a 0.0–5.0 scale.
		num_reviews: Total number of guest reviews.
		image_url: URL of the listing's primary image.
	"""

	model_config = ConfigDict(frozen=True)

	url: str = Field(description="Full URL of the Airbnb listing.")
	title: str = Field(description="Listing title from Airbnb.")
	total_cost: Union[float, None] = Field(
		default=None,
		description="Total booking cost including all fees.",
	)
	nightly_rate: Union[float, None] = Field(
		default=None,
		description="Per-night rate before fees.",
	)
	num_beds: Union[int, None] = Field(
		default=None,
		description="Number of beds in the listing.",
	)
	num_bedrooms: Union[int, None] = Field(
		default=None,
		description="Number of bedrooms.",
	)
	num_bathrooms: Union[float, None] = Field(
		default=None,
		description="Number of bathrooms (may be fractional, e.g. 1.5 for a half bath).",
	)
	amenities: list[str] = Field(
		default_factory=list,
		description="List of amenities (e.g., 'Wi-Fi', 'AC', 'washer/dryer').",
	)
	neighborhood: Union[str, None] = Field(
		default=None,
		description="Neighborhood or area name.",
	)
	rating: Union[float, None] = Field(
		default=None,
		description="Guest rating on a 0.0–5.0 scale.",
	)
	num_reviews: Union[int, None] = Field(
		default=None,
		description="Total number of guest reviews.",
	)
	image_url: Union[str, None] = Field(
		default=None,
		description="URL of the listing's primary image.",
	)


class CostBreakdown(BaseModel):
	"""Per-booking cost breakdown with fee decomposition.

	Computed from the total booking cost visible after clicking Reserve
	on an Airbnb listing page.  Includes per-person and per-night
	calculations for easy comparison across listings.

	Attributes:
		total_cost: Total cost of the stay including all fees.
		num_people: Number of people splitting the cost.
		num_nights: Number of nights for the stay.
		cost_per_person: Total cost divided by number of people.
		cost_per_night: Total cost divided by number of nights.
		cost_per_night_per_person: Total cost divided by people and nights.
		fees: Fee breakdown (e.g., cleaning, service, occupancy taxes).
	"""

	model_config = ConfigDict(frozen=True)

	total_cost: float = Field(description="Total cost of the stay including all fees.")
	num_people: int = Field(description="Number of people splitting the cost.")
	num_nights: int = Field(description="Number of nights for the stay.")
	cost_per_person: float = Field(
		description="Total cost divided by number of people.",
	)
	cost_per_night: float = Field(
		description="Total cost divided by number of nights.",
	)
	cost_per_night_per_person: float = Field(
		description="Total cost divided by people and nights.",
	)
	fees: dict[str, float] = Field(
		default_factory=dict,
		description="Fee breakdown (e.g., cleaning, service, occupancy taxes).",
	)


class ListingWithCost(BaseModel):
	"""An Airbnb listing paired with its computed cost breakdown.

	Combines the listing metadata with per-person cost calculations
	for a specific booking configuration (number of people and nights).

	Attributes:
		listing: The Airbnb listing metadata.
		cost_breakdown: The computed cost breakdown for this listing.
	"""

	model_config = ConfigDict(frozen=True)

	listing: AirbnbListing = Field(description="The Airbnb listing metadata.")
	cost_breakdown: CostBreakdown = Field(
		description="The computed cost breakdown for this listing.",
	)


class ListingFailure(BaseModel):
	"""Record of a listing that failed during batch exploration.

	Captures the URL and a human-readable error message so the agent
	can report which listings failed and why, rather than silently
	returning an empty list.

	Attributes:
		url: Full URL of the Airbnb listing that failed.
		error: Human-readable description of the failure reason.
	"""

	model_config = ConfigDict(frozen=True)

	url: str = Field(description="Full URL of the Airbnb listing that failed.")
	error: str = Field(description="Human-readable description of the failure reason.")


class ExplorationResult(BaseModel):
	"""Result of batch listing exploration with per-listing success/failure reporting.

	Instead of silently returning only successful listings and hiding
	all failures, this model provides the agent with structured
	diagnostic information about which listings succeeded and which
	failed (and why).

	Attributes:
		succeeded: Listings that were successfully parsed with cost data.
		failed: Listings that failed during exploration, with error details.
	"""

	model_config = ConfigDict(frozen=True)

	succeeded: list[ListingWithCost] = Field(
		default_factory=list,
		description="Listings that were successfully parsed with cost data.",
	)
	failed: list[ListingFailure] = Field(
		default_factory=list,
		description="Listings that failed during exploration, with error details.",
	)


class ConstraintViolation(BaseModel):
	"""A single constraint check that a listing failed.

	Attributes:
		constraint: Name of the constraint that was violated (e.g.,
			``"min_bedrooms"``, ``"required_amenities"``).
		reason: Human-readable explanation of why the listing failed
			(e.g., ``"Has 2 bedrooms, need at least 3"``).
	"""

	model_config = ConfigDict(frozen=True)

	constraint: str = Field(
		description="Name of the constraint that was violated.",
	)
	reason: str = Field(
		description="Human-readable explanation of the violation.",
	)


class ConstraintResult(BaseModel):
	"""Per-listing constraint verification result.

	Shows whether a listing passes all constraints and, if not, which
	specific constraints were violated.  This replaces the binary
	pass/fail of ``filter_listings`` with transparent diagnostics
	the agent can report to the user.

	Attributes:
		listing: The listing with its cost breakdown.
		passed: ``True`` if the listing satisfies all constraints.
		violations: List of constraint violations (empty if passed).
	"""

	model_config = ConfigDict(frozen=True)

	listing: ListingWithCost = Field(
		description="The listing with its cost breakdown.",
	)
	passed: bool = Field(
		description="True if the listing satisfies all constraints.",
	)
	violations: list[ConstraintViolation] = Field(
		default_factory=list,
		description="List of constraint violations (empty if passed).",
	)


class ExplorationWithAnalysis(BaseModel):
	"""Enriched exploration result with integrated constraint verification and ranking.

	Combines the exploration results with per-listing constraint
	verification and categorical ranking in a single return value.
	This eliminates the need for a separate filter + rank step,
	reducing token usage by avoiding re-serialization of all
	listings in a subsequent tool call.

	Attributes:
		succeeded: Listings that were successfully parsed with cost data.
		failed: Listings that failed during exploration, with error details.
		constraint_results: Per-listing pass/fail with violation details.
		passed_listings: Listings that passed all constraint checks.
		rankings: Best listing in each category (price, value, amenities,
			location, reviews) — ranked from ``passed_listings`` only.
	"""

	model_config = ConfigDict(frozen=True)

	succeeded: list[ListingWithCost] = Field(
		default_factory=list,
		description="Listings that were successfully parsed with cost data.",
	)
	failed: list[ListingFailure] = Field(
		default_factory=list,
		description="Listings that failed during exploration, with error details.",
	)
	constraint_results: list[ConstraintResult] = Field(
		default_factory=list,
		description="Per-listing pass/fail with violation details.",
	)
	passed_listings: list[ListingWithCost] = Field(
		default_factory=list,
		description="Listings that passed all constraint checks.",
	)
	rankings: dict[str, Union[ListingWithCost, None]] = Field(
		default_factory=dict,
		description="Best listing in each category (ranked from passed listings).",
	)


class WeekAnalysis(BaseModel):
	"""Per-week analysis results with categorical best-pick rankings.

	Contains all listings that matched the week's constraints, plus the
	best listing in each category (price, value, amenities, location,
	reviews).  A category best may be ``None`` if no listings matched.

	Attributes:
		week: The trip week constraints used for this analysis.
		matched_listings: All listings matching the week's constraints.
		best_price: Listing with the lowest total cost.
		best_value: Listing with the best cost-to-rating ratio.
		best_amenities: Listing with the most matching amenities.
		best_location: Listing in the most preferred neighborhood.
		best_reviews: Listing with the highest rating and review count.
	"""

	model_config = ConfigDict(frozen=True)

	week: TripWeek = Field(
		description="The trip week constraints used for this analysis."
	)
	matched_listings: list[ListingWithCost] = Field(
		default_factory=list,
		description="All listings matching the week's constraints.",
	)
	best_price: Union[ListingWithCost, None] = Field(
		default=None,
		description="Listing with the lowest total cost.",
	)
	best_value: Union[ListingWithCost, None] = Field(
		default=None,
		description="Listing with the best cost-to-rating ratio.",
	)
	best_amenities: Union[ListingWithCost, None] = Field(
		default=None,
		description="Listing with the most matching amenities.",
	)
	best_location: Union[ListingWithCost, None] = Field(
		default=None,
		description="Listing in the most preferred neighborhood.",
	)
	best_reviews: Union[ListingWithCost, None] = Field(
		default=None,
		description="Listing with the highest rating and review count.",
	)


class TripAnalysis(BaseModel):
	"""Full multi-week trip analysis summary.

	Aggregates per-week analyses into a complete trip overview with
	per-person cost totals across all weeks (accounting for variable
	participant lists) and an overall summary.

	Attributes:
		weeks: Per-week analysis results.
		per_person_totals: Total cost per participant across all weeks
			they are present (e.g., ``{"Luis": 1250.50, "Laura": 385.67}``).
		overall_summary: Human-readable summary of the full trip analysis.
	"""

	model_config = ConfigDict(frozen=True)

	weeks: list[WeekAnalysis] = Field(description="Per-week analysis results.")
	per_person_totals: dict[str, float] = Field(
		description=("Total cost per participant across all weeks they are present."),
	)
	overall_summary: str = Field(
		description="Human-readable summary of the full trip analysis.",
	)
