"""Friendly application errors."""


class FinSightError(Exception):
    """An expected, user-facing error."""


class UnsupportedFileError(FinSightError):
    """Raised when an upload uses a format the app does not support."""


class InvalidFileError(FinSightError):
    """Raised when a supported file cannot be read safely."""
