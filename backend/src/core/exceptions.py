"""Application exception hierarchy.

Defines the base ``AppException`` and common domain-agnostic sub-exceptions.
Module-specific exceptions should inherit from ``AppException`` (or a
relevant sub-class) and live in their own module's ``exceptions.py``.
"""

__all__: list[str] = [
	"AppException",
	"ForbiddenException",
	"NotFoundException",
	"RateLimitException",
]


class AppException(Exception):
	"""Base exception for all application errors.

	Every custom exception in the project inherits from this class so
	that the centralized exception handlers in
	``core.exception_handlers`` can catch and format them uniformly.

	Attributes:
		message: Human-readable error description.
		code: Machine-readable error code for client-side handling.
	"""

	def __init__(
		self,
		message: str = "Application error",
		code: str = "APP_ERROR",
	) -> None:
		super().__init__(message)
		self.message: str = message
		self.code: str = code


class NotFoundException(AppException):
	"""Raised when a requested resource cannot be found.

	Args:
		message: Human-readable error description.
	"""

	def __init__(self, message: str = "Resource not found") -> None:
		super().__init__(message=message, code="NOT_FOUND")


class ForbiddenException(AppException):
	"""Raised when a caller lacks permission for the requested action.

	Args:
		message: Human-readable error description.
	"""

	def __init__(self, message: str = "Forbidden") -> None:
		super().__init__(message=message, code="FORBIDDEN")


class RateLimitException(AppException):
	"""Raised when a caller exceeds the allowed request rate.

	Args:
		message: Human-readable error description.
	"""

	def __init__(self, message: str = "Rate limit exceeded") -> None:
		super().__init__(message=message, code="RATE_LIMIT_EXCEEDED")


class DatabaseException(AppException):
	"""Raised when a database operation fails.

	Wraps SQLAlchemy errors with a user-safe message while preserving the
	original exception context via ``raise ... from``.
	"""

	def __init__(self, message: str = "A database error occurred") -> None:
		super().__init__(message, code="DATABASE_ERROR")
