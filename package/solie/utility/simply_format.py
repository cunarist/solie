import re


def format_numeric(string: str) -> str:
    string = re.sub(r"[^0123456789\.]", "", string)
    if string.startswith("."):
        string = "0" + string
    if string.endswith("."):
        string = string[:-1]
    return string
