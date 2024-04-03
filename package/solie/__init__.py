import logging

from .entry import bring_to_life

logging.getLogger(__name__).setLevel("DEBUG")

__all__ = ["bring_to_life"]
