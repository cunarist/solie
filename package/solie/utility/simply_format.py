import re


def format_numeric(string: str) -> str:
    string = re.sub(r"[^0123456789\.]", "", string)
    if string.startswith("."):
        string = "0" + string
    if string.endswith("."):
        string = string[:-1]
    return string


def format_fixed_float(number: int | float, width=4, positive_sign=False) -> str:
    if width < 4:
        width = 4

    if number < 0 or (positive_sign and number >= 0):
        # when sign should be included
        absolute_limit = 10 ** (width - 1)
    else:
        absolute_limit = 10**width

    if abs(number) >= absolute_limit:
        number = absolute_limit - 1 if number > 0 else -absolute_limit + 1

    string = f"{number:12.12f}"

    if positive_sign and number >= 0:
        string = "+" + string

    string = string[:width]

    return string
