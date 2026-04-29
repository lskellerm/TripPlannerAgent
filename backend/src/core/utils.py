"""Shared utility functions used across the application.

Module-specific helpers should live in each module's own ``utils.py``.
Only truly cross-cutting utilities belong here.
"""

__all__: list[str] = ["generate_custom_unique_id"]

import re
from typing import Union
from urllib.parse import ParseResult, urlparse

from fastapi import FastAPI
from fastapi.routing import APIRoute
from logfire import (
	ScrubbingOptions,
	ScrubMatch,
	configure,
	instrument_httpx,
	instrument_pydantic_ai,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from .config import Settings


def generate_custom_unique_id(route: APIRoute) -> str:
	"""Generate a concise, unique operation ID for an API route.

	Used as the ``generate_unique_id_function`` in the FastAPI app so that
	client generators (e.g. ``@hey-api/openapi-ts``) produce short,
	readable function names.

	Strategy:
	    * Use only the route's function name (``route.name``) — tags
	      already drive grouping in the generated client, so repeating
	      them in the operation ID would be redundant (e.g.
	      ``healthHealthCheck`` vs. the cleaner ``healthCheck``).
	    * Convert ``snake_case`` to ``camelCase`` so the resulting
	      TypeScript identifiers feel idiomatic without extra transforms
	      by the generator.

	Args:
		route: The FastAPI ``APIRoute`` whose unique id is being
			generated.

	Returns:
		A camelCase operation identifier, e.g. ``getJobById``.
	"""
	return _snake_to_camel(route.name)


def _snake_to_camel(name: str) -> str:
	"""Convert a ``snake_case`` string to ``camelCase``.

	Args:
		name: The snake_case identifier to convert.

	Returns:
		The camelCase equivalent, e.g. ``get_job_by_id`` → ``getJobById``.
	"""
	components: list[str] = re.split(r"_+", name)
	return components[0] + "".join(word.capitalize() for word in components[1:])


def configure_logfire(
	settings: Settings,
	engine: Union[AsyncEngine, None],
	fastapi_app: Union[FastAPI, None],
	disble_scrubbing: bool = False,
	web_chat_enabled: bool = False,
) -> None:
	"""Configure Logfire settings and extras based on the application environment.

	Args:
		disble_scrubbing: If True, disables the default scrubbing of certain matched substrings in Logfire logs. Useful for development and testing environments where full visibility into log data is desired.
	"""
	# ── Logfire Instrumentation (module-level) ──
	# Configure Logfire at runtime so that logfire observability is available in the agent when running via to_web() for dev and testing.
	# logfire.configure() is safe to call multiple times — the FastAPI lifespan will re-configure it with the token in production, but in dev mode this ensures it's configured for the agent when running via to_web().

	logfire_token: Union[str, None] = (
		settings.LOGFIRE_TOKEN.get_secret_value() if settings.LOGFIRE_TOKEN else None
	)

	configure(
		token=logfire_token,
		environment=settings.ENVIRONMENT,
		service_name="TripPlannerAgent-Dev",
	)

	instrument_pydantic_ai()
	instrument_httpx()

	# Instrument only
	if not web_chat_enabled:
		from logfire import (
			instrument_fastapi,
			instrument_sqlalchemy,
			instrument_sqlite3,
		)

		instrument_sqlalchemy(engine=engine) if engine else None
		instrument_sqlite3()
		instrument_fastapi(app=fastapi_app) if fastapi_app else None

	# Dev-specfic Logfire extras (e.g. debug and testing only configuration settings)
	if settings.ENVIRONMENT in ("development", "testing"):
		if disble_scrubbing:
			configure(scrubbing=ScrubbingOptions(callback=_scrubbing_callback))


def _scrubbing_callback(match: ScrubMatch) -> Union[str, None]:
	"""A callback function to allow disabling certain configurable matched 'substrings' from being scrubbed in Logfire logs.

	Args:
		match: A single Logfire scrub match.


	Returns:
		The original matched substring to prevent scrubbing, or None to apply default scrubbing.

	"""
	if (
		match.path
		== (
			"attributes",
			"tool_response",
		)
		and match.pattern_match.group(0) == "Session"
	):
		return match.value  # Return the original matched substring to prevent scrubbing

	# Keep diagnostics for browser_get_network_request safe by replacing the
	# response payload with metadata only (no headers/body/query-string).
	if (
		match.path == ("attributes", "tool_response")
		and match.pattern_match.group(0) == "auth"
	):
		return _sanitize_network_response_metadata(match.value)

	return None


def _sanitize_network_response_metadata(value: str) -> Union[str, None]:
	"""Extract non-sensitive diagnostic metadata from a network response payload.

	This helper intentionally keeps only metadata needed for debugging:
	status, content-type, byte length, and URL host/path. It never returns
	headers, body content, or URL query strings.

	Args:
		value: The raw value considered for scrubbing.

	Returns:
		A sanitized metadata string for network response diagnostics, or
		``None`` when the value is not recognized as a network response payload.
	"""
	if not isinstance(value, str):
		return None

	lowered: str = value.lower()
	if "http://" not in lowered and "https://" not in lowered:
		return None

	if "content-type" not in lowered and "content-length" not in lowered:
		return None

	url_match: Union[re.Match[str], None] = re.search(r"https?://[^\s\"'<>]+", value)
	if url_match is None:
		return None

	parsed: ParseResult = urlparse(url_match.group(0))
	host: str = parsed.netloc or "unknown"
	path: str = parsed.path or "/"

	status_match: Union[re.Match[str], None] = re.search(
		r"(?:status(?:[_ -]?code)?\s*[:=]\s*(\d{3})|\[(\d{3})\])",
		value,
		re.IGNORECASE,
	)
	status_code: Union[str, None] = None
	if status_match is not None:
		status_code: Union[str, None] = status_match.group(1) or status_match.group(2)

	content_type_match: Union[re.Match[str], None] = re.search(
		r"content-type\s*[:=]\s*([^\r\n;]+(?:;[^\r\n]+)?)",
		value,
		re.IGNORECASE,
	)
	content_type: Union[str, None] = None
	if content_type_match is not None:
		content_type: Union[str, None] = content_type_match.group(1).strip()

	content_length_match: Union[re.Match[str], None] = re.search(
		r"content-length\s*[:=]\s*(\d+)", value, re.IGNORECASE
	)
	byte_length: Union[str, None] = None
	if content_length_match is not None:
		byte_length: Union[str, None] = content_length_match.group(1)

	if status_code is None and content_type is None and byte_length is None:
		return None

	return (
		"[Sanitized network response metadata] "
		f"status={status_code or 'unknown'}, "
		f"content_type={content_type or 'unknown'}, "
		f"byte_length={byte_length or 'unknown'}, "
		f"url_host={host}, "
		f"url_path={path}"
	)
