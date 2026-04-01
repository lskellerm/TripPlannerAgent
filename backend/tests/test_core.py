"""Tests for core infrastructure (config, app factory, exceptions, dependencies)."""

from fastapi import status
from httpx import AsyncClient

from src.core.config import FastAPIConfig, Settings, fastapi_config, settings
from src.core.constants import Environment, ScrapingMode
from src.core.dependencies import get_async_session, get_settings
from src.core.exceptions import (
	AppException,
	ForbiddenException,
	NotFoundException,
	RateLimitException,
)
from src.main import app

# ── Settings Tests ──


class TestSettings:
	"""Verify ``Settings`` loads correctly from env."""

	def test_settings_instance_exists(self) -> None:
		"""Settings singleton is available."""
		assert isinstance(settings, Settings)

	def test_app_name_default(self) -> None:
		"""APP_NAME has expected default."""
		assert settings.APP_NAME == "TripPlannerAgent"

	def test_environment_is_enum(self) -> None:
		"""ENVIRONMENT is an Environment enum member."""
		assert isinstance(settings.ENVIRONMENT, Environment)

	def test_scraping_mode_is_enum(self) -> None:
		"""AIRBNB_SCRAPING_MODE is a ScrapingMode enum member."""
		assert isinstance(settings.AIRBNB_SCRAPING_MODE, ScrapingMode)

	def test_debug_computed(self) -> None:
		"""DEBUG is True when ENVIRONMENT is development or testing."""
		if settings.ENVIRONMENT in (Environment.DEVELOPMENT, Environment.TESTING):
			assert settings.DEBUG is True
		else:
			assert settings.DEBUG is False

	def test_api_key_is_secret(self) -> None:
		"""API_KEY is loaded and not exposed as plain string."""
		assert settings.API_KEY.get_secret_value()

	def test_agent_secret_key_is_secret(self) -> None:
		"""AGENT_SECRET_KEY is loaded and not exposed as plain string."""
		assert settings.AGENT_SECRET_KEY.get_secret_value()

	def test_cors_origins_is_list(self) -> None:
		"""CORS_ORIGINS is a non-empty list."""
		assert isinstance(settings.CORS_ORIGINS, list)
		assert len(settings.CORS_ORIGINS) > 0


class TestFastAPIConfig:
	"""Verify ``FastAPIConfig`` loads correctly."""

	def test_fastapi_config_instance_exists(self) -> None:
		"""FastAPIConfig singleton is available."""
		assert isinstance(fastapi_config, FastAPIConfig)

	def test_title_set(self) -> None:
		"""FastAPI title has a value."""
		assert fastapi_config.TITLE

	def test_openapi_url_non_production(self) -> None:
		"""OpenAPI URL is set when not in production."""
		if settings.ENVIRONMENT != Environment.PRODUCTION:
			assert fastapi_config.openapi_url is not None
			assert fastapi_config.openapi_url.endswith("/openapi.json")
		else:
			assert fastapi_config.openapi_url is None


# ── Exception Tests ──


class TestExceptions:
	"""Verify custom exception hierarchy."""

	def test_app_exception_defaults(self) -> None:
		"""AppException has default message and code."""
		exc = AppException()
		assert exc.message == "Application error"
		assert exc.code == "APP_ERROR"

	def test_app_exception_custom(self) -> None:
		"""AppException accepts custom message and code."""
		exc = AppException(message="custom", code="CUSTOM")
		assert exc.message == "custom"
		assert exc.code == "CUSTOM"

	def test_not_found_exception(self) -> None:
		"""NotFoundException has correct defaults."""
		exc = NotFoundException()
		assert exc.code == "NOT_FOUND"
		assert isinstance(exc, AppException)

	def test_forbidden_exception(self) -> None:
		"""ForbiddenException has correct defaults."""
		exc = ForbiddenException()
		assert exc.code == "FORBIDDEN"
		assert isinstance(exc, AppException)

	def test_rate_limit_exception(self) -> None:
		"""RateLimitException has correct defaults."""
		exc = RateLimitException()
		assert exc.code == "RATE_LIMIT_EXCEEDED"
		assert isinstance(exc, AppException)


# ── App Factory Tests ──


class TestAppFactory:
	"""Verify ``create_app()`` configures the FastAPI instance correctly."""

	def test_app_has_healthcheck_route(self) -> None:
		"""App includes the /healthcheck route."""
		routes: list[str] = [getattr(r, "path", "") for r in app.routes]
		assert "/healthcheck" in routes

	def test_app_has_openapi_route(self) -> None:
		"""App exposes OpenAPI schema in non-production."""
		if settings.ENVIRONMENT != Environment.PRODUCTION:
			routes: list[str] = [getattr(r, "path", "") for r in app.routes]
			assert f"{settings.API_V1_PREFIX}/openapi.json" in routes

	def test_app_has_rate_limiter(self) -> None:
		"""App state has the slowapi limiter attached."""
		assert hasattr(app.state, "limiter")


# ── Healthcheck Endpoint Tests ──


class TestHealthcheck:
	"""Verify ``/healthcheck`` endpoint."""

	async def test_healthcheck_returns_200(self, client: AsyncClient) -> None:
		"""GET /healthcheck returns 200 with status ok."""
		response = await client.get("/healthcheck")
		assert response.status_code == status.HTTP_200_OK
		data = response.json()
		assert data["status"] == "ok"


# ── Exception Handler Tests ──


class TestExceptionHandlers:
	"""Verify exception handlers produce structured JSON responses."""

	async def test_not_found_handler(self, client: AsyncClient) -> None:
		"""NotFoundException maps to 404 JSON response."""
		# Add a temporary test route that raises NotFoundException
		from fastapi import APIRouter

		test_router = APIRouter()

		@test_router.get("/test-not-found")
		async def _raise_not_found() -> None:
			raise NotFoundException("thing not found")

		app.include_router(test_router)
		response = await client.get("/test-not-found")
		assert response.status_code == status.HTTP_404_NOT_FOUND
		data = response.json()
		assert data["code"] == "NOT_FOUND"
		assert data["detail"] == "thing not found"

	async def test_forbidden_handler(self, client: AsyncClient) -> None:
		"""ForbiddenException maps to 403 JSON response."""
		from fastapi import APIRouter

		test_router = APIRouter()

		@test_router.get("/test-forbidden")
		async def _raise_forbidden() -> None:
			raise ForbiddenException("access denied")

		app.include_router(test_router)
		response = await client.get("/test-forbidden")
		assert response.status_code == status.HTTP_403_FORBIDDEN
		data = response.json()
		assert data["code"] == "FORBIDDEN"
		assert data["detail"] == "access denied"

	async def test_rate_limit_handler(self, client: AsyncClient) -> None:
		"""RateLimitException maps to 429 JSON response."""
		from fastapi import APIRouter

		test_router = APIRouter()

		@test_router.get("/test-rate-limit")
		async def _raise_rate_limit() -> None:
			raise RateLimitException()

		app.include_router(test_router)
		response = await client.get("/test-rate-limit")
		assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
		data = response.json()
		assert data["code"] == "RATE_LIMIT_EXCEEDED"

	async def test_app_exception_handler(self, client: AsyncClient) -> None:
		"""Generic AppException maps to 500 JSON response."""
		from fastapi import APIRouter

		test_router = APIRouter()

		@test_router.get("/test-app-error")
		async def _raise_app_error() -> None:
			raise AppException(message="something broke", code="BROKE")

		app.include_router(test_router)
		response = await client.get("/test-app-error")
		assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
		data = response.json()
		assert data["code"] == "BROKE"


# ── Dependency Tests ──


class TestDependencies:
	"""Verify shared dependencies."""

	def test_get_settings_returns_singleton(self) -> None:
		"""get_settings returns the same Settings instance."""
		assert get_settings() is settings

	async def test_get_async_session_yields_session(self) -> None:
		"""get_async_session yields an AsyncSession."""
		from sqlalchemy.ext.asyncio import AsyncSession

		async for session in get_async_session():
			assert isinstance(session, AsyncSession)
