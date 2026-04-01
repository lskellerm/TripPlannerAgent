"""Core module — cross-cutting concerns, global config, base exceptions, shared dependencies."""

from src.core.config import Settings, fastapi_config, settings
from src.core.constants import Environment, ScrapingMode
from src.core.dependencies import get_async_session, get_settings
from src.core.exception_handlers import register_exception_handlers
from src.core.exceptions import (
	AppException,
	ForbiddenException,
	NotFoundException,
	RateLimitException,
)
from src.core.utils import generate_custom_unique_id

__all__: list[str] = [
	"AppException",
	"Environment",
	"FastAPIConfig",
	"ForbiddenException",
	"NotFoundException",
	"RateLimitException",
	"ScrapingMode",
	"Settings",
	"fastapi_config",
	"generate_custom_unique_id",
	"get_async_session",
	"get_settings",
	"register_exception_handlers",
	"settings",
]
