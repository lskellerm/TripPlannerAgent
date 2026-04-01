"""Shared utility functions used across the application.

Module-specific helpers should live in each module's own ``utils.py``.
Only truly cross-cutting utilities belong here.
"""

__all__: list[str] = ["generate_custom_unique_id"]

import re

from fastapi.routing import APIRoute


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
