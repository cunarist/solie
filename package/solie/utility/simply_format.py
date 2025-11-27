"""Simple string formatting utilities."""

import re


def format_numeric(string: str) -> str:
    """Extract and format numeric characters from string."""
    string = re.sub(r"[^0123456789\.]", "", string)
    if string.startswith("."):
        string = "0" + string
    return string.removesuffix(".")
