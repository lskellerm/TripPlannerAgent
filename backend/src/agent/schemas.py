"""Agent data models — trip planning constraint schemas.

Defines the ``TripWeek`` model that captures per-week trip constraints
including dates, location, participants, and accommodation requirements.

Fields that represent accommodation requirements (``min_bedrooms``,
``min_bathrooms``) are **auto-inferred** from ``num_people`` when not
provided explicitly, so the agent can construct a ``TripWeek`` from
minimal trip data and still get sensible filtering behaviour.
"""

import math
from datetime import date
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TripWeek(BaseModel):
	"""Per-week trip constraints for an Airbnb search.

	Each ``TripWeek`` represents one week of a multi-week trip, specifying
	the travel dates, location, participants, and accommodation requirements
	that the agent uses to search and filter Airbnb listings.

	When ``min_bedrooms`` or ``min_bathrooms`` are omitted, sensible
	defaults are inferred from ``num_people``:

	* ``min_bedrooms`` = ``ceil(num_people / 2)`` (at least 1)
	* ``min_bathrooms`` = 1

	This allows the agent to construct a ``TripWeek`` from just the trip
	dates, location, and guest count — no explicit constraints needed.

	Attributes:
		week_label: Display name for the week (e.g., "Week 1").
		check_in: Check-in date for the week.
		check_out: Check-out date for the week.
		location: City or area to search (e.g., "Mexico City").
		neighborhood_constraints: Preferred neighborhoods to filter by.
		participants: Names of people staying this week.
		num_people: Total number of participants for cost splitting.
		min_bedrooms: Minimum required bedrooms (inferred from num_people
			if omitted).
		min_bathrooms: Minimum required bathrooms (defaults to 1 if
			omitted).
		min_rating: Minimum acceptable listing rating (0.0–5.0).
		required_amenities: Must-have amenities (e.g., "Wi-Fi", "AC").
		max_price_per_person: Optional budget cap per person for the week.
	"""

	model_config = ConfigDict(frozen=True)

	week_label: str = Field(
		default="Week 1",
		description="Display name for the week (e.g., 'Week 1').",
	)
	check_in: date = Field(description="Check-in date for the week.")
	check_out: date = Field(description="Check-out date for the week.")
	location: str = Field(description="City or area to search (e.g., 'Mexico City').")
	neighborhood_constraints: Union[list[str], None] = Field(
		default_factory=list,
		description="Preferred neighborhoods to filter by.",
	)
	participants: list[str] = Field(
		default_factory=list,
		description="Names of people staying this week.",
	)
	num_people: int = Field(
		description="Total number of participants for cost splitting."
	)
	min_bedrooms: int = Field(
		default=1,
		description="Minimum required bedrooms (inferred from num_people if omitted).",
	)
	min_bathrooms: int = Field(
		default=1,
		description="Minimum required bathrooms (defaults to 1 if omitted).",
	)
	min_rating: float = Field(
		default=0.0,
		description="Minimum acceptable listing rating (0.0–5.0).",
	)
	required_amenities: list[str] = Field(
		default_factory=list,
		description="Must-have amenities (e.g., 'Wi-Fi', 'AC').",
	)
	max_price_per_person: Union[float, None] = Field(
		default=None,
		description="Optional budget cap per person for the week.",
	)

	@model_validator(mode="before")
	@classmethod
	def _infer_accommodation_defaults(cls, data: Any) -> Any:
		"""Infer ``min_bedrooms`` from ``num_people`` when not provided.

		Uses ``ceil(num_people / 2)`` as the default — two people per
		bedroom is a reasonable assumption for group trips.

		Args:
			data: Raw input data (dict when constructed from keyword
				arguments).

		Returns:
			The (possibly mutated) input data with inferred defaults.
		"""
		if isinstance(data, dict):
			num_people: int = data.get("num_people", 1)
			if "min_bedrooms" not in data:
				data["min_bedrooms"] = max(1, math.ceil(num_people / 2))
		return data
