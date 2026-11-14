"""Shared engine errors and units (contract §2.1)."""

from collections.abc import Callable


class EngineError(Exception):
    code: str = "internal_error"


class MarketDataUnavailable(EngineError):
    code = "market_data_unavailable"


class InvalidGrid(EngineError):
    code = "invalid_grid"


class GeneratorNotTrained(EngineError):
    code = "generator_not_trained"


class Cancelled(Exception):
    pass


ProgressFn = Callable[[float], None]
TRADING_DAYS = 252
