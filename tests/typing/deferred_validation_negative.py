"""Incorrect input validation call contracts (expected type errors)."""

# pyright: strict

from pytuflow import TCF
from pytuflow.batch_validation import validate_batch_inputs


def invalid_calls(model: TCF) -> None:
    validate_batch_inputs(model, [123])
    validate_batch_inputs(model, ["-s1 Existing"], options=4)
    validate_batch_inputs(3, ["-s1 Existing"])
