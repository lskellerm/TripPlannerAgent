"""Airbnb-domain constants — regex patterns and magic values used by parsers."""

import re
from re import Pattern

__all__: list[str] = [
	"AIRBNB_AMENITY_IDS",
	"AIRBNB_ROOMS_PREFIX",
	"BATHS_PATTERN",
	"BEDROOMS_PATTERN",
	"BEDS_ONLY_PATTERN",
	"CITY_SUFFIXES",
	"DISCOUNTED_PRICE_PATTERN",
	"BEDS_PATTERN",
	"FOR_N_NIGHTS_PATTERN",
	"H1_TITLE_LOCATION_PATTERN",
	"KNOWN_CDMX_NEIGHBORHOOD_ABBREVIATIONS",
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
	"RESERVE_BUTTON_SELECTOR",
	"BOOKING_TOTAL_SELECTOR",
	"BOOKING_PRICE_DETAILS_SELECTOR",
	"BOOKING_CONFIRM_PAY_SELECTOR",
	"LISTING_BOOKING_SIDEBAR_SELECTOR",
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


## ── Booking-page selectors/signals used after clicking Reserve ── ##

# Booking-page selectors/signals used after clicking Reserve.
RESERVE_BUTTON_SELECTOR: str = '[data-testid="homes-pdp-cta-btn"]'
BOOKING_TOTAL_SELECTOR: str = '[data-testid="pd-value-TOTAL"]'
BOOKING_PRICE_DETAILS_SELECTOR: str = "text=/Price details/i"
BOOKING_CONFIRM_PAY_SELECTOR: str = "text=/Confirm and pay/i"

# Listing-page booking widget selectors used before clicking Reserve.
# Includes the sidebar test id and the Booking Information aside.
LISTING_BOOKING_SIDEBAR_SELECTOR: str = (
	'[data-testid="book-it-default"], '
	'aside[aria-label="Booking Information"], '
	'aside[aria-label*="Booking"]'
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
	r"(\d+(?:\.\d+)?)\s*(?:private\s+|shared\s+)?bath(?:room)?s?", re.IGNORECASE
)

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

# ── og:title Structured Data Extraction ──

# Airbnb og:title format:
# "<type> in <city> · ★<rating> · N bedroom(s) · N bed(s) · N [private|shared] bath(s)"
OG_TITLE_ROOM_PATTERN: Pattern[str] = re.compile(
	r"(\d+)\s*bedrooms?|(\d+)\s*beds?|(\d+(?:\.\d+)?)\s*(?:private\s+|shared\s+)?baths?",
	re.IGNORECASE,
)

# Extracts the location/neighbourhood from og:title text like
# "Rental unit in Mexico City · ★5.0 · ..." → "Mexico City"
OG_TITLE_LOCATION_PATTERN: Pattern[str] = re.compile(r"\bin\s+([^·]+)", re.IGNORECASE)

# Extracts neighbourhood from a host-given listing title (H1 / <title>).
# Matches "in/at/near {Location}" (case-insensitive preposition) where
# Location starts with a capital letter and consists of capitalised words
# separated by spaces, hyphens, or slashes, optionally followed by a
# comma + another capitalised segment.  An optional article (the, a, an,
# el, la) between the preposition and the location is consumed but not
# captured.
# Rejects candidates starting with lowercase ("a picturesque", "the center").
# Examples:
#   "Remodelled Apartment in Central Condesa, CDMX" → "Central Condesa, CDMX"
#   "Apartment in Roma-Condesa, very conveniently located." → "Roma-Condesa"
#   "Well-equipped house in a picturesque neighborhood" → no match
#   "Magnificent apartment in the Historic Center" → "Historic Center"
#   "Cozy flat w/great views at La Roma" → "La Roma"
#   "Apartment near the Angel of Independence" → "Angel of Independence"
H1_TITLE_LOCATION_PATTERN: Pattern[str] = re.compile(
	r"\b(?i:in|at|near)\s+(?:(?i:the|a|an|el|la)\s+)?([A-Z][A-Za-z\u00C0-\u00FF]+(?:[\s/-][A-Za-z\u00C0-\u00FF]+)*(?:,\s*[A-Z][A-Za-z\u00C0-\u00FF]+(?:[\s/-][A-Za-z\u00C0-\u00FF]+)*)*)"
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
	"Colonia Roma": "Roma Norte",
	"Roma-Condesa": "Roma Norte",  # often used interchangeably with "Roma Norte" for listings that are on the border
	"La Roma": "Roma Norte",
	"Colima": "Roma Norte",
	"ColRoma-Sr": "Roma Sur",
	"Roma-Sur": "Roma Sur",
	"Roma Sur": "Roma Sur",
	"Condesa": "Condesa",
	"Central Condesa": "Condesa",
	"Revolution": "Colonia Tabacalera",
	"Revolución": "Colonia Tabacalera",
	"Monumento De La Revolución": "Colonia Tabacalera",
	"Tabacalera": "Colonia Tabacalera",
	"Reforma": "Colonia Cuauhtémoc",
	"Cuauhtémoc": "Colonia Cuauhtémoc",
	"Cuauhtemoc": "Colonia Cuauhtémoc",
	"Cauuhtemoc": "Colonia Cuauhtémoc",
	"Avenida Reforma": "Colonia Cuauhtémoc",
	"Avenida De La Reforma": "Colonia Cuauhtémoc",
	"The Angel of Independence": "Colonia Juárez",
	"Angel of Independence": "Colonia Juárez",
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
	"Narvarte": "Narvarte",
	"San Antonio Abad": "San Antonio Abad",
	"Colonia Juarez": "Juárez",
}

# Common city-name suffixes to strip from extracted neighbourhood candidates
# before looking up in a neighbourhood mapping.  Ordered longest-first so that
# the most specific suffix is tried before shorter overlapping ones.
CITY_SUFFIXES: list[str] = [
	" de la Ciudad de México",
	" of Mexico City",
	", Mexico City",
	" de México",
	", CDMX",
	", México",
]

RELEVANT_AIRBNB_AMENITIES: set[str] = {
	"Wi-Fi",
	"Wifi",
	"WiFi",
	"wi-fi",
	"wifi",
	"Internet",
	"wireless internet",
	"Air conditioning",
	"ac",
	"AC",
	"Kitchen",
	"Heating",
	"washer/dryer",
	"Washer/Dryer",
	"Washer",
	"Dryer",
	"Washer-Dryer",
	"Washer and Dryer",
	"Washer & Dryer",
	"Early check-in",
	"Late check-in",
	"Self check-in",
	"24-hour check-in",
	"Gym",
	"Pool",
	"Hot tub",
	"Coffee maker",
	"TV",
	"Cable TV",
	"Smart TV",
	"TV with standard cable",
	"Hot Water",
	"Water Dispenser",
	"Free parking on premises",
	"Free street parking",
}


# ── Amenity Alias Map ──
# Maps common short-hand amenity names the LLM might request to the
# set of full Airbnb amenity strings that satisfy the requirement.
# All keys and values are lower-cased for case-insensitive matching.
AMENITY_ALIASES: dict[str, list[str]] = {
	"ac": [
		"air conditioning",
		"central air conditioning",
		"portable air conditioning",
		"ac - ",
		"mini split",
		"a/c",
		"window ac",
		"window air conditioning",
	],
	"air conditioning": [
		"air conditioning",
		"central air conditioning",
		"portable air conditioning",
		"ac - ",
		"mini split",
		"a/c",
		"window ac",
		"window air conditioning",
	],
	"wifi": ["wifi", "wi-fi", "wireless internet", "fast wifi"],
	"wi-fi": ["wifi", "wi-fi", "wireless internet", "fast wifi"],
	"washer": ["washer", "washer/dryer", "washer / dryer"],
	"dryer": ["dryer", "washer/dryer", "washer / dryer"],
	"parking": [
		"free parking",
		"paid parking",
		"free parking on premises",
		"free street parking",
		"parking",
	],
	"pool": ["pool", "shared pool", "private pool"],
	"hot tub": ["hot tub", "private hot tub", "shared hot tub"],
	"gym": ["gym", "fitness center", "exercise equipment"],
	"kitchen": ["kitchen", "full kitchen", "kitchenette"],
	"tv": ["tv", "hdtv", "television"],
	"heating": ["heating", "central heating", "radiant heating"],
}


# ── Airbnb URL Filter Amenity IDs ──
# Mapping of amenity short-hand names to the numeric IDs that Airbnb
# accepts as ``amenities[]`` query parameters in search URLs.  These
# IDs correspond to Airbnb's internal amenity filter identifiers
# visible in the filter modal's network requests.
# Using these enables *server-side* pre-filtering — Airbnb only
# returns listings that have the amenity, dramatically reducing the
# number of irrelevant results.
AIRBNB_AMENITY_IDS: dict[str, int] = {
	"wifi": 4,
	"wi-fi": 4,
	"kitchen": 8,
	"washer": 33,
	"dryer": 34,
	"ac": 5,
	"air conditioning": 5,
	"heating": 30,
	"tv": 58,
	"pool": 7,
	"hot tub": 25,
	"gym": 15,
	"parking": 9,
	"elevator": 21,
	"self check-in": 51,
}
