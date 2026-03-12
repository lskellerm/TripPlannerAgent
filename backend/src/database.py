"""SQLite async database engine configuration.

Uses ``aiosqlite`` for async SQLite access. Provides an async session
factory for message history storage. Can upgrade to PostgreSQL later if needed.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

DATABASE_URL = "sqlite+aiosqlite:///./tripplanner.db"

engine: AsyncEngine = create_async_engine(
	DATABASE_URL,
	echo=False,
	connect_args={"check_same_thread": False},
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
	engine,
	class_=AsyncSession,
	expire_on_commit=False,
)
