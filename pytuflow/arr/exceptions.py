"""Exceptions used throughout the :mod:`pytuflow.arr` module."""


class ArrError(Exception):
    """Base class for all errors raised by :mod:`pytuflow.arr`."""


class ArrConfigError(ArrError):
    """Raised when a JSON config file is missing, malformed, or fails validation."""


class ArrApiError(ArrError):
    """Raised when a request to the ARR Data Hub API fails, or the response is missing
    expected data."""
