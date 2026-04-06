"""Airbnb-domain constants — regex patterns and magic values used by parsers."""

import re
from re import Pattern

__all__: list[str] = [
	"AIRBNB_ROOMS_PREFIX",
	"BATHS_PATTERN",
	"BEDS_PATTERN",
	"MAX_CARD_TEXT_LENGTH",
	"MAX_NEIGHBORHOOD_LENGTH",
	"MIN_NEIGHBORHOOD_LENGTH",
	"NEIGHBORHOOD_TESTID_PATTERN",
	"NIGHTLY_RATE_PATTERN",
	"PRICE_PATTERN",
	"RATING_PATTERN",
	"REVIEW_COUNT_PATTERN",
	"ROOM_ID_PATTERN",
	"TOTAL_PRICE_PATTERN",
]

# ── URL / ID Patterns ──

AIRBNB_ROOMS_PREFIX: str = "https://www.airbnb.com/rooms/"
ROOM_ID_PATTERN: Pattern[str] = re.compile(r"/rooms/(\d+)")

# ── Price Patterns ──

PRICE_PATTERN: Pattern[str] = re.compile(r"\$[\d,]+(?:\.\d{2})?")
NIGHTLY_RATE_PATTERN: Pattern[str] = re.compile(
	r"\$(\d[\d,]*)\s*(?:per\s*)?night", re.IGNORECASE
)
# Pattern that matches "$X,XXX ... for N nights" total-stay pricing on search cards
TOTAL_PRICE_PATTERN: Pattern[str] = re.compile(
	r"\$(\d[\d,]*)\s+.*?(?:for|breakdown\s+for)\s+(\d+)\s*night",
	re.IGNORECASE,
)

# ── Rating / Review Patterns ──

RATING_PATTERN: Pattern[str] = re.compile(r"(\d+\.\d+)\s*(?:★|stars?)?", re.IGNORECASE)
REVIEW_COUNT_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*reviews?", re.IGNORECASE)

# ── Property Detail Patterns ──

BEDS_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*bed(?:room)?s?", re.IGNORECASE)
BATHS_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*bath(?:room)?s?", re.IGNORECASE)

# ── Neighbourhood Extraction ──

# data-testid values that identify the card subtitle/location element on search results
NEIGHBORHOOD_TESTID_PATTERN: Pattern[str] = re.compile(
	r"^(subtitle|listing-card-title)$", re.IGNORECASE
)
# Plausible length bounds for a neighbourhood name extracted from card text
MIN_NEIGHBORHOOD_LENGTH: int = 3
MAX_NEIGHBORHOOD_LENGTH: int = 60
# Maximum length of a card child's text to consider for neighbourhood extraction
MAX_CARD_TEXT_LENGTH: int = 100
