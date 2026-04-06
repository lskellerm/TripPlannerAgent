"""Shared utility functions used across the application.

Module-specific helpers should live in each module's own ``utils.py``.
Only truly cross-cutting utilities belong here.
"""

__all__: list[str] = ["generate_custom_unique_id"]

import re
from typing import Union

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


def _scrubbing_callback(match: ScrubMatch) -> None:
	"""A callback function to allow disabling certain configurable matched 'substrings' from being scrubbed in Logfire logs.

	Args:
		record: The original log record dictionary.

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
