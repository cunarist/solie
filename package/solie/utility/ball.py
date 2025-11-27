"""Numeric rounding utilities."""

import math


def ball_ceil(number: float, decimals: int) -> float:
    """Round number up to specified decimal places."""
    number = number * 10**decimals
    number = math.ceil(number)
    return number / 10**decimals


def ball_floor(number: float, decimals: int) -> float:
    """Round number down to specified decimal places."""
    number = number * 10**decimals
    number = math.floor(number)
    return number / 10**decimals
