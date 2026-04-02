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

		# Check minimum bedrooms
		if listing.num_bedrooms is not None:
			if listing.num_bedrooms < constraints.min_bedrooms:
				continue

		# Check minimum bathrooms
		if listing.num_bathrooms is not None:
			if listing.num_bathrooms < constraints.min_bathrooms:
				continue

		# Check minimum rating
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
			if listing.neighborhood is not None:
				neighborhood_lower: str = listing.neighborhood.lower()
				if not any(
					n.lower() in neighborhood_lower
					for n in constraints.neighborhood_constraints
				):
					continue
			# If neighbourhood is None, we can't verify — skip check

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
		- ``best_amenities``: Most amenities listed.
		- ``best_location``: Listing with a neighbourhood set
		  (first match; prefers listings with location data).
		- ``best_reviews``: Highest rating, with review count as
		  tie-breaker.

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
	# Only consider listings with a rating. This favors higher-rated listings and avoids division by zero.
	# In this comparison logic, the smaller the ratio, the better the value (lower cost per person for higher rating; cost_per_person: rating).
	rated: list[ListingWithCost] = [
		lwc for lwc in listings if lwc.listing.rating is not None
	]
	best_value: Union[ListingWithCost, None] = None
	if rated:
		best_value: Union[ListingWithCost, None] = min(
			rated,
			key=lambda lwc: (
				lwc.cost_breakdown.cost_per_person / (lwc.listing.rating or 1.0)
			),
		)

	# Best amenities: most amenities
	best_amenities: Union[ListingWithCost, None] = max(
		listings, key=lambda lwc: len(lwc.listing.amenities)
	)

	# Best location: prefer listings with a neighbourhood set
	located: list[ListingWithCost] = [
		lwc for lwc in listings if lwc.listing.neighborhood is not None
	]
	best_location: Union[ListingWithCost, None] = located[0] if located else None

	# Best reviews: highest rating, review count as tie-breaker
	best_reviews: Union[ListingWithCost, None] = None
	if rated:
		best_reviews: ListingWithCost = max(
			rated,
			key=lambda lwc: (
				lwc.listing.rating or 0.0,
				lwc.listing.num_reviews or 0,
			),
		)

	return {
		"best_price": best_price,
		"best_value": best_value,
		"best_amenities": best_amenities,
		"best_location": best_location,
		"best_reviews": best_reviews,
	}
