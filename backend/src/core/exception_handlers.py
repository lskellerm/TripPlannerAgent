"""Exception-to-HTTP-response mapping handlers.

Registers centralized exception handlers on the FastAPI application so
that all ``AppException`` sub-classes (and Pydantic validation errors)
are serialized into a uniform JSON envelope.
"""

__all__: list[str] = ["register_exception_handlers"]

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from src.core.exceptions import (
	AppException,
	DatabaseException,
	ForbiddenException,
	NotFoundException,
	RateLimitException,
)


def register_exception_handlers(app: FastAPI) -> None:
	"""Attach exception handlers to the FastAPI application.

	Maps custom exception types to structured JSON error responses with
	appropriate HTTP status codes.

	Args:
		app: The FastAPI application instance to register handlers on.
	"""

	@app.exception_handler(NotFoundException)
	async def not_found_handler(
		request: Request,
		exc: NotFoundException,
	) -> JSONResponse:
		"""Handle ``NotFoundException`` → 404.

		Args:
			request: The incoming HTTP request.
			exc: The raised exception instance.

		Returns:
			A 404 JSON response with error details.
		"""
		return JSONResponse(
			status_code=status.HTTP_404_NOT_FOUND,
			content={"detail": exc.message, "code": exc.code},
		)

	@app.exception_handler(ForbiddenException)
	async def forbidden_handler(
		request: Request,
		exc: ForbiddenException,
	) -> JSONResponse:
		"""Handle ``ForbiddenException`` → 403.

		Args:
			request: The incoming HTTP request.
			exc: The raised exception instance.

		Returns:
			A 403 JSON response with error details.
		"""
		return JSONResponse(
			status_code=status.HTTP_403_FORBIDDEN,
			content={"detail": exc.message, "code": exc.code},
		)

	@app.exception_handler(RateLimitException)
	async def rate_limit_handler(
		request: Request,
		exc: RateLimitException,
	) -> JSONResponse:
		"""Handle ``RateLimitException`` → 429.

		Args:
			request: The incoming HTTP request.
			exc: The raised exception instance.

		Returns:
			A 429 JSON response with error details.
		"""
		return JSONResponse(
			status_code=status.HTTP_429_TOO_MANY_REQUESTS,
			content={"detail": exc.message, "code": exc.code},
		)

	@app.exception_handler(AppException)
	async def app_exception_handler(
		request: Request,
		exc: AppException,
	) -> JSONResponse:
		"""Handle any unhandled ``AppException`` → 500.

		Acts as a catch-all for application exceptions that don't have
		a more specific handler registered above.

		Args:
			request: The incoming HTTP request.
			exc: The raised exception instance.

		Returns:
			A 500 JSON response with error details.
		"""
		return JSONResponse(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			content={"detail": exc.message, "code": exc.code},
		)

	@app.exception_handler(RequestValidationError)
	async def validation_error_handler(
		request: Request,
		exc: RequestValidationError,
	) -> JSONResponse:
		"""Handle Pydantic ``RequestValidationError`` → 422.

		Reformats the default validation error into the same JSON
		envelope used by all other exception handlers.

		Args:
			request: The incoming HTTP request.
			exc: The raised validation error.

		Returns:
			A 422 JSON response with structured validation error details.
		"""
		return JSONResponse(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			content=jsonable_encoder(
				{
					"detail": "Validation error",
					"code": "VALIDATION_ERROR",
					"errors": exc.errors(),
				}
			),
		)

	@app.exception_handler(DatabaseException)
	async def database_exception_handler(
		request: Request,
		exc: DatabaseException,
	) -> JSONResponse:
		"""Handle ``DatabaseException`` → 500.

		Args:
			request: The incoming HTTP request.
			exc: The raised database exception instance.

		Returns:
			A 500 JSON response with error details.
		"""
		return JSONResponse(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			content={"detail": exc.message, "code": exc.code},
		)
