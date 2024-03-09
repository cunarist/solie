from dataclasses import dataclass


@dataclass
class DownloadPreset:
    symbol: str
    unit_size: str  # "daily" or "monthly"
    year: int
    month: int
    day: int = 0  # Valid only when `unit_size` is "daily"
