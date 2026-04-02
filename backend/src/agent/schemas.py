"""Agent data models — trip planning constraint schemas.

Defines the ``TripWeek`` model that captures per-week trip constraints
including dates, location, participants, and accommodation requirements.
"""

from datetime import date
from typing import Union

from pydantic import BaseModel, ConfigDict, Field


class TripWeek(BaseModel):
	"""Per-week trip constraints for an Airbnb search.

	Each ``TripWeek`` represents one week of a multi-week trip, specifying
	the travel dates, location, participants, and accommodation requirements
	that the agent uses to search and filter Airbnb listings.

	Attributes:
		week_label: Display name for the week (e.g., "Week 1").
		check_in: Check-in date for the week.
		check_out: Check-out date for the week.
		location: City or area to search (e.g., "Mexico City").
		neighborhood_constraints: Preferred neighborhoods to filter by.
		participants: Names of people staying this week.
		num_people: Total number of participants for cost splitting.
		min_bedrooms: Minimum required bedrooms.
		min_bathrooms: Minimum required bathrooms.
		min_rating: Minimum acceptable listing rating (0.0–5.0).
		required_amenities: Must-have amenities (e.g., "Wi-Fi", "AC").
		max_price_per_person: Optional budget cap per person for the week.
	"""

	model_config = ConfigDict(frozen=True)

	week_label: str = Field(description="Display name for the week (e.g., 'Week 1').")
	check_in: date = Field(description="Check-in date for the week.")
	check_out: date = Field(description="Check-out date for the week.")
	location: str = Field(description="City or area to search (e.g., 'Mexico City').")
	neighborhood_constraints: Union[list[str], None] = Field(
		default_factory=list,
		description="Preferred neighborhoods to filter by.",
	)
	participants: list[str] = Field(
		description="Names of people staying this week.",
	)
	num_people: int = Field(
		description="Total number of participants for cost splitting."
	)
	min_bedrooms: int = Field(description="Minimum required bedrooms.")
	min_bathrooms: int = Field(description="Minimum required bathrooms.")
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
