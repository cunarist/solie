"""Core trading logic and algorithms."""

from .account_listener import AccountListener
from .analyze_market import (
    CalculationInput,
    CalculationOutput,
    DecisionContext,
    SimulationError,
    make_decisions,
    make_indicators,
    simulate_chunk,
)
from .binance_watcher import BinanceWatcher, ExchangeConfig, StateConfig
from .download_from_binance import (
    DownloadPreset,
    DownloadUnitSize,
    download_aggtrade_csv,
    fill_holes_with_aggtrades,
    process_aggtrade_csv,
)
from .order_placer import OrderPlacer, OrderPlacerConfig
from .simulation_calculator import (
    CalculationConfig,
    CalculationResult,
    SimulationCalculator,
    WidgetReferences,
)

__all__ = [
    "AccountListener",
    "BinanceWatcher",
    "CalculationConfig",
    "CalculationInput",
    "CalculationOutput",
    "CalculationResult",
    "DecisionContext",
    "DownloadPreset",
    "DownloadUnitSize",
    "ExchangeConfig",
    "OrderPlacer",
    "OrderPlacerConfig",
    "SimulationCalculator",
    "SimulationError",
    "StateConfig",
    "WidgetReferences",
    "download_aggtrade_csv",
    "fill_holes_with_aggtrades",
    "make_decisions",
    "make_indicators",
    "process_aggtrade_csv",
    "simulate_chunk",
]
