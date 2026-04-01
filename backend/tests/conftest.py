"""Shared test fixtures for the TripPlannerAgent backend test suite."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
	"""Provide an async HTTP test client wired to the FastAPI app.

	Yields:
		An ``httpx.AsyncClient`` that sends requests directly through ASGI.
	"""
	async with AsyncClient(
		transport=ASGITransport(app=app),
		base_url="http://testserver",
	) as ac:
		yield ac
