"""FastAPI application factory and lifespan management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.core.config import fastapi_config, settings
from src.database import engine
from src.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
	"""Manage application startup and shutdown lifecycle.

	On startup:
	- Configures Logfire observability (when ``LOGFIRE_TOKEN`` is set).
	- Creates all database tables if they do not yet exist.

	On shutdown:
	- Disposes the async database engine to release connections.

	Args:
		app: The FastAPI application instance.

	Yields:
		None — control is handed to the application during the ``yield``.
	"""
	# ── Startup ──
	logfire_token = (
		settings.LOGFIRE_TOKEN.get_secret_value() if settings.LOGFIRE_TOKEN else None
	)
	if logfire_token:
		logfire.configure(token=logfire_token)
		logfire.instrument_fastapi(app)
		logfire.instrument_httpx()

	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	yield

	# ── Shutdown ──
	await engine.dispose()


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
	title=fastapi_config.TITLE,
	version=fastapi_config.VERSION,
	description=fastapi_config.DESCRIPTION,
	openapi_url=fastapi_config.openapi_url,
	lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]  # slowapi stubs don't align with FastAPI's handler signature

app.add_middleware(
	CORSMiddleware,
	allow_origins=settings.CORS_ORIGINS,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.get("/healthcheck", tags=["Health"])
async def healthcheck() -> dict[str, str]:
	"""Return service health status.

	Returns:
		A dict with ``status`` key set to ``"ok"``.
	"""
	return {"status": "ok"}
