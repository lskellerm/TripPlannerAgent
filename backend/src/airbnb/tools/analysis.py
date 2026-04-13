"""Analysis tools — filtering, cost breakdowns, trip totals, and ranking.

Provides deterministic Python functions for filtering Airbnb listings
against user constraints, computing per-person cost breakdowns, ranking
listings by category (price, value, amenities, location, reviews), and
aggregating multi-week per-person trip totals with variable participant
lists.
"""

from typing import Union

from src.agent.schemas import TripWeek
from src.airbnb.schemas import (
	AirbnbListing,
	CostBreakdown,
	ListingWithCost,
	WeekAnalysis,
)


def filter_search_results(
	listings: list[AirbnbListing],
	constraints: TripWeek,
) -> list[AirbnbListing]:
	"""Pre-filter search results before detailed exploration.

	Applies a lightweight subset of constraints that can be evaluated
	using only the partial data available from the search results page
	(no cost breakdown or bathroom data needed).  This reduces the
	number of listings the agent needs to explore individually.

	Checked constraints:
		- ``min_bedrooms`` — skips listings with fewer bedrooms
		  (listings with unknown bedrooms are kept).
		- ``min_rating`` — skips listings below the minimum rating
		  (listings with unknown rating are kept).
		- ``neighborhood_constraints`` — skips listings outside
		  preferred neighbourhoods (listings with unknown
		  neighbourhood are kept).
		- ``max_price_per_person`` — estimates from nightly rate ×
		  nights ÷ people; skips if clearly over budget.

	Args:
		listings: Candidate listings from search results.
		constraints: The trip week constraints to pre-filter against.

	Returns:
		A new list containing listings that are plausible matches.
	"""
	num_nights: int = max((constraints.check_out - constraints.check_in).days, 1)
	matched: list[AirbnbListing] = []

	for listing in listings:
		# Check minimum bedrooms (skip only when we know it's insufficient)
		if listing.num_bedrooms is not None:
			if listing.num_bedrooms < constraints.min_bedrooms:
				continue

		# Check minimum rating (skip only when we know it's below threshold)
		if constraints.min_rating > 0 and listing.rating is not None:
			if listing.rating < constraints.min_rating:
				continue

		# Check neighbourhood constraints (skip only when neighbourhood is
		# known and doesn't match any preference).
		# Treat city-level neighbourhood (e.g. "Mexico City" when searching
		# in "Mexico City") as *unknown* — the search card didn't provide a
		# real neighbourhood, so we keep the listing for detailed exploration.
		if constraints.neighborhood_constraints and listing.neighborhood is not None:
			neighborhood_lower: str = listing.neighborhood.lower()
			location_lower: str = constraints.location.lower()
			is_city_level: bool = neighborhood_lower == location_lower
			if not is_city_level and not any(
				n.lower() in neighborhood_lower
				for n in constraints.neighborhood_constraints
			):
				continue

		# Estimate total cost from nightly rate and check budget
		if (
			constraints.max_price_per_person is not None
			and listing.nightly_rate is not None
		):
			estimated_total: float = listing.nightly_rate * num_nights
			estimated_per_person: float = estimated_total / max(
				constraints.num_people, 1
			)
			if estimated_per_person > constraints.max_price_per_person:
				continue

		matched.append(listing)

	return matched


def filter_listings(
	listings: list[ListingWithCost],
	constraints: TripWeek,
) -> list[ListingWithCost]:
	"""Filter listings that match the given trip week constraints.

	Checks each listing against minimum bedrooms, minimum bathrooms,
	minimum rating, required amenities, neighbourhood preferences, and
	maximum price per person.

	Args:
		listings: Candidate listings with cost breakdowns.
		constraints: The trip week constraints to filter against.

	Returns:
		A new list containing only listings that satisfy all constraints.
	"""
	matched: list[ListingWithCost] = []

	for lwc in listings:
		listing: AirbnbListing = lwc.listing
		cost: CostBreakdown = lwc.cost_breakdown

		# Check minimum bedrooms. Missing data cannot satisfy a required constraint.
		if listing.num_bedrooms is None:
			continue
		if listing.num_bedrooms < constraints.min_bedrooms:
			continue

		# Check minimum bathrooms. Missing data cannot satisfy a required constraint.
		if listing.num_bathrooms is None:
			continue
		if listing.num_bathrooms < constraints.min_bathrooms:
			continue

		# Check minimum rating
		if constraints.min_rating > 0 and listing.rating is None:
			continue
		if listing.rating is not None:
			if listing.rating < constraints.min_rating:
				continue

		# Check required amenities (case-insensitive)
		if constraints.required_amenities:
			listing_amenities_lower: set[str] = {a.lower() for a in listing.amenities}
			if not all(
				req.lower() in listing_amenities_lower
				for req in constraints.required_amenities
			):
				continue

		# Check neighbourhood constraints (case-insensitive)
		if constraints.neighborhood_constraints:
			if listing.neighborhood is None:
				continue

			neighborhood_lower: str = listing.neighborhood.lower()
			if not any(
				n.lower() in neighborhood_lower
				for n in constraints.neighborhood_constraints
			):
				continue
		# Check max price per person
		if constraints.max_price_per_person is not None:
			if cost.cost_per_person > constraints.max_price_per_person:
				continue

		matched.append(lwc)

	return matched


def calculate_cost_breakdown(
	total_cost: float,
	num_people: int,
	num_nights: int,
	fees: Union[dict[str, float], None] = None,
) -> CostBreakdown:
	"""Compute per-person and per-night cost breakdown.

	Args:
		total_cost: Total cost of the stay including all fees.
		num_people: Number of people splitting the cost.
		num_nights: Number of nights for the stay.
		fees: Optional fee breakdown (e.g., cleaning, service).

	Returns:
		A ``CostBreakdown`` with per-person and per-night calculations.

	Raises:
		ValueError: If ``num_people`` or ``num_nights`` is less than 1.
	"""
	if num_people < 1:
		raise ValueError("num_people must be at least 1")
	if num_nights < 1:
		raise ValueError("num_nights must be at least 1")

	return CostBreakdown(
		total_cost=total_cost,
		num_people=num_people,
		num_nights=num_nights,
		cost_per_person=round(total_cost / num_people, 2),
		cost_per_night=round(total_cost / num_nights, 2),
		cost_per_night_per_person=round(total_cost / num_people / num_nights, 2),
		fees=fees or {},
	)


def calculate_trip_totals(
	week_analyses: list[WeekAnalysis],
	participant_names: list[str],
) -> dict[str, float]:
	"""Compute per-person total cost across all weeks.

	Accounts for variable participant lists per week — a participant
	is only charged for weeks they are present in.  Uses the
	``best_price`` listing for each week as the assumed booking.

	Args:
		week_analyses: Per-week analysis results, each containing a
			``week`` with participants and a ``best_price`` pick.
		participant_names: All unique participant names across the trip.

	Returns:
		A dict mapping participant name to their total cost across all
		weeks they participate in.  Returns ``0.0`` for participants
		not present in any analysed week.

		ex: {
			 "Alice": 350.00,
			 "Bob": 420.00,
			 "Charlie": 0.00,  # Not present in any week
			}


	"""
	totals: dict[str, float] = {name: 0.0 for name in participant_names}

	for analysis in week_analyses:
		week: TripWeek = analysis.week
		# Use best_price listing for cost calculation
		pick: Union[ListingWithCost, None] = analysis.best_price
		if pick is None:
			continue

		cost_per_person: float = pick.cost_breakdown.cost_per_person

		for participant in week.participants:
			if participant in totals:
				totals[participant] = round(totals[participant] + cost_per_person, 2)

	return totals


def rank_by_category(
	listings: list[ListingWithCost],
) -> dict[str, Union[ListingWithCost, None]]:
	"""Rank listings and select the best in each category.

	Categories:
		- ``best_price``: Lowest total cost.
		- ``best_value``: Best cost-to-rating ratio (lowest
		  ``cost_per_person / rating``).
		- ``best_amenities``: Most amenities listed.  When no listing
		  has amenities, falls back to a proxy score based on
		  ``num_bedrooms + num_bathrooms + num_beds``.
		- ``best_location``: Listing in the most desirable
		  neighbourhood, scored by a tiered desirability ranking.
		- ``best_reviews``: Composite score weighting rating (60%)
		  and normalised review count (40%).

	Args:
		listings: Listings with cost breakdowns to rank.

	Returns:
		A dict mapping category name to the best ``ListingWithCost``
		in that category, or ``None`` if no listing qualifies.
	"""
	if not listings:
		return {
			"best_price": None,
			"best_value": None,
			"best_amenities": None,
			"best_location": None,
			"best_reviews": None,
		}

	# Best price: lowest total cost
	best_price: Union[ListingWithCost, None] = min(
		listings, key=lambda lwc: lwc.cost_breakdown.total_cost
	)
	# Best value: lowest cost_per_person / rating ratio
	rated: list[ListingWithCost] = [
		lwc
		for lwc in listings
		if lwc.listing.rating is not None and lwc.listing.rating > 0
	]
	best_value: Union[ListingWithCost, None] = None
	if rated:
		best_value: ListingWithCost = min(
			rated,
			key=lambda lwc: lwc.cost_breakdown.cost_per_person / lwc.listing.rating,
		)

	# Best amenities: most amenities, with proxy fallback
	has_amenities: bool = any(len(lwc.listing.amenities) > 0 for lwc in listings)
	if has_amenities:
		best_amenities: Union[ListingWithCost, None] = max(
			listings, key=lambda lwc: len(lwc.listing.amenities)
		)
	else:
		# Proxy: sum of bedrooms + bathrooms + beds (more space ≈ more amenities)
		best_amenities: Union[ListingWithCost, None] = max(
			listings,
			key=lambda lwc: (
				(lwc.listing.num_bedrooms or 0)
				+ (lwc.listing.num_bathrooms or 0)
				+ (lwc.listing.num_beds or 0)
			),
		)

	# Best location: tiered neighbourhood desirability scoring in CDMX
	# Tier 1 (score 3): Most desirable walkable neighbourhoods.
	# Tier 2 (score 2): Very good but slightly further or less trendy.
	# Tier 3 (score 1): Acceptable, known neighbourhood.
	# Unknown (score 0): No neighbourhood or unrecognised.
	_LOCATION_TIERS: dict[str, int] = {
		"Roma Norte": 3,
		"Condesa": 3,
		"Juárez": 3,
		"Roma Sur": 2,
		"Colonia Cuauhtémoc": 2,
		"Centro Histórico": 2,
		"Colonia Tabacalera": 1,
		"Coyoacán": 1,
		"Narvarte": 1,
		"San Antonio Abad": 1,
		"Colonia Juárez": 3,
	}

	def _location_score(lwc: ListingWithCost) -> int:
		"""Return desirability score for a listing's neighbourhood."""
		hood: Union[str, None] = lwc.listing.neighborhood
		if hood is None:
			return 0
		return _LOCATION_TIERS.get(hood, 0)

	located: list[ListingWithCost] = [
		lwc for lwc in listings if lwc.listing.neighborhood is not None
	]
	best_location: Union[ListingWithCost, None] = None
	if located:
		best_location = max(
			located,
			key=lambda lwc: (
				_location_score(lwc),
				lwc.listing.rating or 0.0,
			),
		)

	# Best reviews: composite score = 0.6 * normalised_rating + 0.4 * normalised_reviews
	best_reviews: Union[ListingWithCost, None] = None
	if rated:
		max_reviews: int = max(
			(lwc.listing.num_reviews or 0 for lwc in rated), default=1
		)
		max_reviews = max(max_reviews, 1)  # avoid division by zero

		best_reviews = max(
			rated,
			key=lambda lwc: (
				0.6 * ((lwc.listing.rating or 0.0) / 5.0)
				+ 0.4 * ((lwc.listing.num_reviews or 0) / max_reviews)
			),
		)

	return {
		"best_price": best_price,
		"best_value": best_value,
		"best_amenities": best_amenities,
		"best_location": best_location,
		"best_reviews": best_reviews,
	}
