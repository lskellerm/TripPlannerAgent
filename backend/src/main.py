"""FastAPI application factory and lifespan management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Union

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.agent.agent import agent as trip_agent
from src.agent.agent import configure_agent_model
from src.core.config import fastapi_config, settings
from src.core.exception_handlers import register_exception_handlers
from src.core.utils import generate_custom_unique_id
from src.database import engine
from src.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
	"""Manage application startup and shutdown lifecycle.

	On startup:
	- Configures Logfire observability (when ``LOGFIRE_TOKEN`` is set).
	- Creates all database tables if they do not yet exist.
	- Ensures the Playwright HTML output directory exists.
	- Starts the Playwright MCP server subprocess via the agent context.

	On shutdown:
	- Stops the Playwright MCP server subprocess.
	- Disposes the async database engine to release connections.

	Args:
		app: The FastAPI application instance.

	Yields:
		None — control is handed to the application during the ``yield``.
	"""
	# ── Startup ──
	logfire_token: Union[str, None] = (
		settings.LOGFIRE_TOKEN.get_secret_value() if settings.LOGFIRE_TOKEN else None
	)
	logfire.configure(token=logfire_token)
	logfire.instrument_fastapi(app)
	logfire.instrument_pydantic_ai()
	logfire.instrument_httpx()
	logfire.instrument_sqlalchemy(engine=engine)
	logfire.instrument_sqlite3()

	# ── Database Setup ──
	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	# ── Playwright HTML Output Directory ──
	Path(settings.PLAYWRIGHT_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

	# ── Ollama Derived Model Configuration ──
	await configure_agent_model()

	# ── Playwright MCP Server Lifecycle ──
	async with trip_agent:
		yield

	# ── Shutdown ──
	await engine.dispose()


def create_app() -> FastAPI:
	"""Factory function to create and configure the FastAPI application.

	Returns:
		A configured FastAPI application instance withn CORS, rate limitings, routers, and exception handlers set up.
	"""

	# Initialize FastAPI app with metadata and lifespan management
	app = FastAPI(
		**fastapi_config.model_dump(),
		lifespan=lifespan,
		generate_unique_id_function=generate_custom_unique_id,
	)
	limiter = Limiter(key_func=get_remote_address)

	# Store limiter instance in app state for access in routes and dependencies
	app.state.limiter: Limiter = limiter
	app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # ty: ignore[invalid-argument-type]  # slowapi stubs don't align with FastAPI's handler signature

	# ── Exception Handlers ──
	register_exception_handlers(app)

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
		return {
			"status": "ok",
			"message": "The application is running and healthy.",
		}

	return app


app: FastAPI = create_app()
