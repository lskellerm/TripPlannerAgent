"""Shared FastAPI dependencies used across multiple modules.

Provides the async database session dependency and any other cross-cutting
``Depends()`` callables.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
	"""Yield an async database session, closing it after the request.

	Yields:
	    An ``AsyncSession`` scoped to the current request lifecycle.
	"""
	async with async_session_factory() as session:
		yield session
