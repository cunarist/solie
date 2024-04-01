import math


def ball_ceil(number: float, decimals: int) -> float:
    number = number * 10**decimals
    number = math.ceil(number)
    number = number / 10**decimals
    return number


def ball_floor(number: float, decimals: int) -> float:
    number = number * 10**decimals
    number = math.floor(number)
    number = number / 10**decimals
    return number
