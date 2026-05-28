"""Core trading logic and algorithms."""

from .account_listener import AccountListener, ParseOrderTypeParams
from .analyze_market import (
    ChunkSimulation,
    DecisionContext,
    SimulationError,
    SimulationOutput,
    make_decisions,
    make_indicators,
)
from .binance_watcher import BinanceWatcher, ExchangeConfig, StateConfig
from .download_from_binance import (
    DownloadPreset,
    DownloadUnitSize,
    download_aggtrade_csv,
    write_aggtrade_csv_to_candle_store,
)
from .order_placer import OrderPlacer, OrderPlacerConfig
from .simulation_calculator import (
    CalculationConfig,
    CalculationResult,
    SimulationCalculator,
    WidgetReferences,
)

__all__ = (
    "AccountListener",
    "BinanceWatcher",
    "CalculationConfig",
    "CalculationResult",
    "ChunkSimulation",
    "DecisionContext",
    "DownloadPreset",
    "DownloadUnitSize",
    "ExchangeConfig",
    "OrderPlacer",
    "OrderPlacerConfig",
    "ParseOrderTypeParams",
    "SimulationCalculator",
    "SimulationError",
    "SimulationOutput",
    "StateConfig",
    "WidgetReferences",
    "download_aggtrade_csv",
    "make_decisions",
    "make_indicators",
    "write_aggtrade_csv_to_candle_store",
)
