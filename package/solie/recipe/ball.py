import math


def ceil(number: float, decimals: int) -> int:
    number = number * 10**decimals
    number = math.ceil(number)
    number = number / 10**decimals
    number = int(number)
    return number


def floor(number: float, decimals: int) -> int:
    number = number * 10**decimals
    number = math.floor(number)
    number = number / 10**decimals
    number = int(number)
    return number
