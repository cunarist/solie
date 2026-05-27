"""Constants used throughout the application."""

from collections.abc import Mapping
from types import MappingProxyType

from polars import DataType, Float32, Float64, Int64, String

type PolarsSchema = Mapping[str, type[DataType]]

# HTTP Status Codes
HTTP_OK = 200

# Time Constants (in seconds)
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
SECONDS_PER_MONTH = 2678400  # 31 days
SECONDS_PER_YEAR = 31622400  # 366 days
TWENTY_SECONDS = 20
TWO_SECONDS = 2
TWO_MINUTES = 120
TWENTY_MINUTES = 1200

# UI Constraints
MAX_SELECTED_COINS = 12
MIN_SELECTED_COINS = 1
LONG_SYMBOL_LIST_THRESHOLD = 5
MAX_TICK_LABELS = 12

# Progress Bar
PROGRESS_BAR_MAX = 1000

# Calculation/Simulation
MAX_PREPARATION_STEPS = 6
MIN_PEAK_COUNT = 12

# Data Collection
MAX_REQUEST_RETRIES = 10
MIN_SERVER_TIME_SAMPLES = 30

# Decision Constants
COLUMN_PARTS_COUNT = 3

# Magic Number Replacements
MIN_SERIES_LENGTH = 2
EXIT_DIALOG_ANSWER = 2

# Polars Schemas
CANDLE_ROW_SCHEMA: PolarsSchema = MappingProxyType(
    {
        "timestamp": Int64,
        "open": Float64,
        "high": Float64,
        "low": Float64,
        "close": Float64,
        "volume": Float64,
    },
)

DOWNLOADED_CANDLE_ROW_SCHEMA: PolarsSchema = MappingProxyType(
    {
        "symbol": String,
        **CANDLE_ROW_SCHEMA,
    },
)

ASSET_RECORD_SCHEMA: PolarsSchema = MappingProxyType(
    {
        "timestamp": Int64,
        "CAUSE": String,
        "SYMBOL": String,
        "SIDE": String,
        "FILL_PRICE": Float64,
        "ROLE": String,
        "MARGIN_RATIO": Float64,
        "ORDER_ID": Int64,
        "RESULT_ASSET": Float64,
    },
)

ASSET_CHANGE_SCHEMA: PolarsSchema = MappingProxyType(
    {
        "timestamp": Int64,
        "ASSET_CHANGE": Float64,
    },
)

AUTO_ORDER_RECORD_SCHEMA: PolarsSchema = MappingProxyType(
    {
        "timestamp": Int64,
        "SYMBOL": String,
        "ORDER_ID": Int64,
    },
)


def create_empty_candle_frame_schema(target_symbols: list[str]) -> PolarsSchema:
    """Create the legacy prefixed candle frame schema for several symbols."""
    schema: dict[str, type[DataType]] = {"timestamp": Int64}
    for symbol in target_symbols:
        schema.update(
            {
                f"{symbol}/OPEN": Float32,
                f"{symbol}/HIGH": Float32,
                f"{symbol}/LOW": Float32,
                f"{symbol}/CLOSE": Float32,
                f"{symbol}/VOLUME": Float32,
            },
        )
    return schema


def create_symbol_candle_frame_schema(symbol: str) -> PolarsSchema:
    """Create the prefixed candle frame schema for one symbol."""
    return {
        "timestamp": Int64,
        f"{symbol}/OPEN": Float64,
        f"{symbol}/HIGH": Float64,
        f"{symbol}/LOW": Float64,
        f"{symbol}/CLOSE": Float64,
        f"{symbol}/VOLUME": Float64,
    }
