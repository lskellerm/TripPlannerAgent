"""Airbnb-domain constants — regex patterns and magic values used by parsers."""

import re
from re import Pattern

__all__: list[str] = [
	"AIRBNB_ROOMS_PREFIX",
	"BATHS_PATTERN",
	"BEDROOMS_PATTERN",
	"BEDS_ONLY_PATTERN",
	"DISCOUNTED_PRICE_PATTERN",
	"BEDS_PATTERN",
	"FOR_N_NIGHTS_PATTERN",
	"H1_TITLE_LOCATION_PATTERN",
	"MAX_CARD_TEXT_LENGTH",
	"MAX_NEIGHBORHOOD_LENGTH",
	"MIN_NEIGHBORHOOD_LENGTH",
	"NEIGHBORHOOD_TESTID_PATTERN",
	"NIGHTLY_RATE_PATTERN",
	"OG_TITLE_LOCATION_PATTERN",
	"OG_TITLE_ROOM_PATTERN",
	"PRICE_PATTERN",
	"RATE_OPTION_TOTAL_PATTERN",
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
# Pattern that matches "$X for N nights" (direct total-stay price on listing pages)
FOR_N_NIGHTS_PATTERN: Pattern[str] = re.compile(
	r"\$(\d[\d,]*)\s+(?:for\s+)(\d+)\s*nights?",
	re.IGNORECASE,
)
# Pattern that matches "$X $Y Show price breakdown for N nights" where $X is the
# strikethrough (original) price and $Y is the discounted price.  Captures $Y.
DISCOUNTED_PRICE_PATTERN: Pattern[str] = re.compile(
	r"\$\d[\d,]*(?:\.\d{2})?\s+\$(\d[\d,]*(?:\.\d{2})?)\s+.*?(?:for|breakdown\s+for)\s+(\d+)\s*night",
	re.IGNORECASE,
)
# Pattern that matches rate option format: "Non-refundable · $X total" or
# "Refundable · $X total" — the "$X total" where the amount precedes "total".
RATE_OPTION_TOTAL_PATTERN: Pattern[str] = re.compile(
	r"\$(\d[\d,]*(?:\.\d{2})?)\s+total",
	re.IGNORECASE,
)

# ── Rating / Review Patterns ──

RATING_PATTERN: Pattern[str] = re.compile(r"(\d+\.\d+)\s*(?:★|stars?)?", re.IGNORECASE)
REVIEW_COUNT_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*reviews?", re.IGNORECASE)

# ── Property Detail Patterns ──

BEDROOMS_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*bedrooms?", re.IGNORECASE)
BEDS_ONLY_PATTERN: Pattern[str] = re.compile(
	r"(\d+)\s*(?:king|queen|sofa|twin|double|single|bunk\s+)?\s*beds?\b",
	re.IGNORECASE,
)
BEDS_PATTERN: Pattern[str] = re.compile(r"(\d+)\s*bed(?:room)?s?", re.IGNORECASE)
BATHS_PATTERN: Pattern[str] = re.compile(
	r"(\d+)\s*(?:private\s+|shared\s+)?bath(?:room)?s?", re.IGNORECASE
)

# ── Neighbourhood Extraction ──

# data-testid values that identify the card subtitle/location element on search results
NEIGHBORHOOD_TESTID_PATTERN: Pattern[str] = re.compile(
	r"^(subtitle|listing-card-title)$", re.IGNORECASE
)
# Plausible length bounds for a neighbourhood n`ame` extracted from card text
MIN_NEIGHBORHOOD_LENGTH: int = 3
MAX_NEIGHBORHOOD_LENGTH: int = 60
# Maximum length of a card child's text to consider for neighbourhood extraction
MAX_CARD_TEXT_LENGTH: int = 100

# ── og:title Structured Data Extraction ──

# Airbnb og:title format:
# "<type> in <city> · ★<rating> · N bedroom(s) · N bed(s) · N [private|shared] bath(s)"
OG_TITLE_ROOM_PATTERN: Pattern[str] = re.compile(
	r"(\d+)\s*bedrooms?|(\d+)\s*beds?|(\d+)\s*(?:private\s+|shared\s+)?baths?",
	re.IGNORECASE,
)

# Extracts the location/neighbourhood from og:title text like
# "Rental unit in Mexico City · ★5.0 · ..." → "Mexico City"
OG_TITLE_LOCATION_PATTERN: Pattern[str] = re.compile(r"\bin\s+([^·]+)", re.IGNORECASE)

# Extracts neighbourhood from a host-given listing title (H1 / <title>).
# Matches "in {Location}" where Location starts with a capital letter and
# consists of capitalised words separated by spaces, hyphens, or slashes,
# optionally followed by a comma + another capitalised segment.
# Rejects candidates starting with articles/prepositions ("a", "the").
# Examples:
#   "Remodelled Apartment in Central Condesa, CDMX" → "Central Condesa, CDMX"
#   "Apartment in Roma-Condesa, very conveniently located." → "Roma-Condesa"
#   "Well-equipped house in a picturesque neighborhood" → no match
H1_TITLE_LOCATION_PATTERN: Pattern[str] = re.compile(
	r"\bin\s+([A-Z][A-Za-z]+(?:[\s/-][A-Za-z]+)*(?:,\s*[A-Z][A-Za-z]+(?:[\s/-][A-Za-z]+)*)*)"
)

# Mapping of known CDMX neighbourhood abbreviations and relative location name variants to their canonical forms.
# This is used to standardize extracted neighbourhood names by replacing known abbreviations (e.g., "Roma Nte")
# and common variants (e.g., "Revolución") with their full canonical names (e.g., "Roma Norte", "Colonia Tabacalera").
KNOWN_CDMX_NEIGHBORHOOD_ABBREVIATIONS: dict[str, str] = {
	"Roma Norte": "Roma Norte",
	"Roma Nte": "Roma Norte",
	"Roma-Nte": "Roma Norte",
	"Roma-North": "Roma Norte",
	"Roma North": "Roma Norte",
	"Colima": "Roma Norte",
	"ColRoma-Sr": "Roma Sur",
	"Roma-Sur": "Roma Sur",
	"Roma Sur": "Roma Sur",
	"Condesa": "Condesa",
	"Central Condesa": "Condesa",
	"Roma-Condesa": "Condesa",
	"Revolution": "Colonia Tabacalera",
	"Revolución": "Colonia Tabacalera",
	"Monumento De La Revolución": "Colonia Tabacalera",
	"Tabacalera": "Colonia Tabacalera",
	"Reforma": "Colonia Cuauhtémoc",
	"Cuauhtémoc": "Colonia Cuauhtémoc",
	"Cauuhtemoc": "Colonia Cuauhtémoc",
	"Avenida Reforma": "Colonia Cuauhtémoc",
	"Avenida De La Reforma": "Colonia Cuauhtémoc",
	"The Angel of Independence": "Colonia Juárez",
	"Ángel De La Independencia": "Colonia Juárez",
	"Juarez": "Juárez",
	"Colonia Juárez": "Juárez",
	"Coyoacan": "Coyoacán",
	"Coyoacán": "Coyoacán",
	"Historic Center": "Centro Histórico",
	"Historic Centre": "Centro Histórico",
	"Historical Center": "Centro Histórico",
	"Centro Historico": "Centro Histórico",
	"Centro Histórico": "Centro Histórico",
	"Histórico": "Centro Histórico",
	"Historical": "Centro Histórico",
	"Downtown": "Centro Histórico",
	"Centro": "Centro Histórico",
}
