"""Application-wide configuration via pydantic-settings loaded from environment variables and ``.env`` file.

Provides two settings classes:
- ``Settings``: Core application config (Ollama, auth, CORS, rate limiting).
- ``FastAPIConfig``: FastAPI-specific config with ``FASTAPI_`` env prefix.
"""

from typing import Union

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.constants import Environment, ScrapingMode


class Settings(BaseSettings):
	"""Core application settings loaded from environment variables and ``.env`` file.

	Attributes:
	- ``APP_NAME``: The name of the application.
	- ``ENVIRONMENT``: The application environment (development, production, testing).
	- ``OLLAMA_BASE_URL``: Base URL for the Ollama LLM provider.
	- ``OLLAMA_MODEL_NAME``: The Ollama model to use for LLM interactions.
	- ``API_KEY``: Secret API key for authenticating requests.
	- ``AGENT_SECRET_KEY``: Secret key for signing agent tokens.
	- ``AGENT_TOKEN_EXPIRE_MINUTES``: Expiration time for agent tokens in minutes.
	- ``CORS_ORIGINS``: List of allowed CORS origins.
	- ``API_V1_PREFIX``: URL prefix for version 1 of the API.
	- ``AIRBNB_SCRAPING_MODE``: Mode for Airbnb scraping (live or cached).
	- ``PLAYWRIGHT_MCP_VERSION``: Pinned version of ``@playwright/mcp`` used by the agent's MCP subprocess.
	- ``RATE_LIMIT_PER_MINUTE``: Number of allowed requests per minute for rate limiting.
	- ``LOGFIRE_TOKEN``: Optional Logfire token for observability integration.
	- ``DEBUG``: Computed property indicating if the app is in debug mode (true for development and testing environments).
	"""

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
	)

	# ── Application ──
	APP_NAME: str = "TripPlannerAgent"
	ENVIRONMENT: Environment = Environment.DEVELOPMENT

	# ── Ollama (LLM Provider) ──
	OLLAMA_BASE_URL: str = "http://localhost:11434"
	OLLAMA_MODEL_NAME: str = "qwen2.5:32b"

	# ── Authentication ──
	API_KEY: SecretStr
	AGENT_SECRET_KEY: SecretStr
	AGENT_TOKEN_EXPIRE_MINUTES: int = 30

	# ── CORS ──
	CORS_ORIGINS: list[str] = ["http://localhost:3000"]

	# ── API ──
	API_V1_PREFIX: str = "/api/v1"

	# ── Airbnb Scraping ──
	AIRBNB_SCRAPING_MODE: ScrapingMode = ScrapingMode.LIVE

	# ── Playwright MCP ──
	PLAYWRIGHT_MCP_VERSION: str = "0.0.70"

	# ── Rate Limiting ──
	RATE_LIMIT_PER_MINUTE: int = 10

	# ── Observability ──
	LOGFIRE_TOKEN: Union[SecretStr, None] = None

	@computed_field
	@property
	def DEBUG(self) -> bool:
		"""Whether the application is running in debug mode.

		Returns:
			True if ``ENVIRONMENT`` is ``development`` or ``testing``.
		"""
		return self.ENVIRONMENT in (Environment.DEVELOPMENT, Environment.TESTING)


class FastAPIConfig(BaseSettings):
	"""FastAPI-specific settings with ``FASTAPI_`` env prefix.

	Controls the application metadata shown in auto-generated API docs
	and the OpenAPI schema availability.
	"""

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		env_prefix="FASTAPI_",
		case_sensitive=False,
		extra="ignore",
	)

	TITLE: str = "TripPlannerAgent API"
	VERSION: str = "0.1.0"
	DESCRIPTION: str = "AI-powered Airbnb search and trip cost analysis API"

	@computed_field
	@property
	def openapi_url(self) -> Union[str, None]:
		"""Compute OpenAPI schema URL.

		Returns:
			The OpenAPI URL in non-production environments, None in production
			to disable the schema endpoint.
		"""
		# Access the sibling Settings to check environment
		if settings.ENVIRONMENT == Environment.PRODUCTION:
			return None
		return f"{settings.API_V1_PREFIX}/openapi.json"


settings = Settings()  # ty: ignore[missing-argument]
fastapi_config = FastAPIConfig()
