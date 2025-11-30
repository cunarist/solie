"""Utility types for helping type checkers for safer code."""


class Implements[T]:
    """A generic class to indicate that a class implements an interface.

    This is primarily for type-checking purposes and does not enforce any
    behavior at runtime.
    """

    def __init__(self, cls: type[T]) -> None:
        """Accept the class type to indicate implementation."""
