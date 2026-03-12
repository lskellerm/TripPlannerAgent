"""Application-wide constants and enums."""

from enum import StrEnum


class Environment(StrEnum):
	"""Application environment modes."""

	DEVELOPMENT = "development"
	PRODUCTION = "production"
	TESTING = "testing"


class ScrapingMode(StrEnum):
	"""Airbnb scraping mode — live browser or cached HTML fallback."""

	LIVE = "live"
	CACHED = "cached"


# ── HTTP Status Codes (semantic aliases) ──
HTTP_200_OK = 200
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_422_UNPROCESSABLE_ENTITY = 422
HTTP_429_TOO_MANY_REQUESTS = 429
HTTP_500_INTERNAL_SERVER_ERROR = 500
HTTP_502_BAD_GATEWAY = 502
HTTP_503_SERVICE_UNAVAILABLE = 503
