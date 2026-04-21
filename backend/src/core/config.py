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
	- ``OLLAMA_MAX_TOKENS``: Maximum number of tokens the model can generate per request.
	- ``OLLAMA_NUM_CTX``: Context window size (in tokens) for the Ollama model. At startup, a derived Ollama model is created with this value baked in (via ``/api/create``), because Ollama's OpenAI-compatible endpoint does not support ``options.num_ctx``. Default 32768 (32K) to reduce KV cache pressure for 16 GB GPUs.
	- ``OLLAMA_NUM_GPU``: Number of layers to keep on GPU when creating the derived model. ``999`` requests full GPU offload.
	- ``OLLAMA_QUANTIZE``: Optional quantization override passed to ``/api/create``. Use ``"native"`` to keep the pulled model tag's built-in quantization.
	- ``OLLAMA_TEMPERATURE``: Sampling temperature for model generation. Default 0.7 per Qwen3 recommended non-thinking mode settings.
	- ``OLLAMA_TIMEOUT``: Timeout in seconds for model requests (covers httpx read timeout during streaming). Local LLMs with large contexts and thinking enabled (e.g. qwen3.5) need generous read timeouts — the model may pause for extended periods between output chunks while processing tool results or reasoning internally.
	- ``OLLAMA_FREQUENCY_PENALTY``: Penalizes repeated tokens based on frequency (0.0–2.0). Helps prevent degenerate text loops.
	- ``OLLAMA_PRESENCE_PENALTY``: Penalizes tokens that have already appeared (0.0–2.0). Encourages topic diversity.
	- ``API_KEY``: Secret API key for authenticating requests.
	- ``AGENT_SECRET_KEY``: Secret key for signing agent tokens.
	- ``AGENT_TOKEN_EXPIRE_MINUTES``: Expiration time for agent tokens in minutes.
	- ``CORS_ORIGINS``: List of allowed CORS origins.
	- ``API_V1_PREFIX``: URL prefix for version 1 of the API.
	- ``AIRBNB_SCRAPING_MODE``: Mode for Airbnb scraping (live or cached).
	- ``PLAYWRIGHT_MCP_VERSION``: Pinned version of ``@playwright/mcp`` used by the agent's MCP subprocess.
	- ``PLAYWRIGHT_OUTPUT_DIR``: Directory where Playwright MCP saves browser-extracted files (HTML dumps, snapshots). Parsers read HTML from this directory.
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
	OLLAMA_MODEL_NAME: str = "qwen3.5:9b"
	# OLLAMA_MODEL_NAME: str = "qwen3.5:35b-a3b"
	# OLLAMA_MODEL_NAME: str = "qwen3:14b-q4_K_M"
	OLLAMA_MAX_TOKENS: int = 16384
	OLLAMA_NUM_CTX: int = 32768  # Baked into a derived Ollama model at startup
	OLLAMA_NUM_GPU: int = -1  # Use all available GPU layers by default; set to 0 to disable GPU offload and run on CPU
	OLLAMA_QUANTIZE: str = "native"  # Use pulled tag quantization unless overridden
	# OLLAMA_TEMPERATURE: float = 0.7  # Qwen3 non-thinking mode recommended
	# OLLAMA_TEMPERATURE: float = 0.2  # Qwen3 thinking mode recommended (high)

	OLLAMA_TEMPERATURE: float = 0.3  # Qwen3 thinking mode recommended (medium)
	OLLAMA_TIMEOUT: float = 1200.0
	OLLAMA_FREQUENCY_PENALTY: float = 0.3
	OLLAMA_PRESENCE_PENALTY: float = 0.2

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

	# ── Playwright MCP Server Configuration ──
	PLAYWRIGHT_MCP_VERSION: str = "0.0.70"
	PLAYWRIGHT_OUTPUT_DIR: str = "./.playwright-mcp/html_output"
	MAX_CONCURRENT_BROWSERS: int = 3

	# ── Code Mode (pydantic-ai-harness) ──
	# When enabled, the custom Airbnb FunctionToolset is wrapped behind a
	# single ``run_code`` tool powered by the Monty sandbox.
	#
	# The agent can then chain multiple Airbnb tool calls in one Python snippet
	# (loops, asyncio.gather, in-memory filtering) instead of paying
	# one model round-trip per call.
	#
	# Browser/MCP tools are excluded because they must run sequentially and are deferred-execution.
	#
	# DISABLED BY DEFAULT (2026-04-20): ``pydantic-ai-harness 0.1.1`` (the
	# only published version) calls ``FunctionSnapshot.resume(future=...)``
	# inside ``code_mode/_toolset.py::_handle_function_snapshot``, but no
	# released ``pydantic-monty`` version exposes that keyword — the latest
	# (``0.0.16``) only accepts ``resume(result, *, mount, os)``.  Every
	# ``run_code`` invocation therefore fails with::
	#
	#     TypeError: FunctionSnapshot.resume() got an unexpected keyword
	#     argument 'future'
	#
	# Re-enable once upstream ships a compatible Monty release (track at
	# https://github.com/pydantic/pydantic-ai-harness/issues/215).
	CODE_MODE_ENABLED: bool = False
	CODE_MODE_MAX_RETRIES: int = 3

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
