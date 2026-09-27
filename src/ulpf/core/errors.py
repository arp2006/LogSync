from typing import Any


class ULPFError(Exception):
    """Base exception for all ULPF domain and application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class APIError(ULPFError):
    """Structured error destined for API responses."""
