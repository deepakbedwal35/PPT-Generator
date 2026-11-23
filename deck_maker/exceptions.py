"""Application exception types."""

from __future__ import annotations


class AppError(Exception):
    """Domain error representing an HTTP error response."""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)
