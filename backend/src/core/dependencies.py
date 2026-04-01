"""Shared FastAPI dependencies used across multiple modules.

Provides the async database session dependency, settings singleton
accessor, and any other cross-cutting ``Depends()`` callables.
"""

__all__: list[str] = ["get_async_session", "get_settings"]

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, settings
from src.database import async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
	"""Yield an async database session, closing it after the request.

	Yields:
	    An ``AsyncSession`` scoped to the current request lifecycle.
	"""
	async with async_session_factory() as session:
		yield session


def get_settings() -> Settings:
	"""Return the application-wide ``Settings`` singleton.

	Useful as a FastAPI ``Depends()`` override target in tests.

	Returns:
		The global ``Settings`` instance.
	"""
	return settings
