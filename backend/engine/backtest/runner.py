"""Vectorized, batched close-only backtests; contract §2.4."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.backtest.templates import TemplateId
from engine.common import ProgressFn, TRADING_DAYS


@dataclass
class BacktestResult:
    variants: list[dict[str, float]]
    strat_ret_real: np.ndarray
    sharpe_real: np.ndarray
    selected: int
    position_real_selected: np.ndarray
    strat_ret_paths_selected: np.ndarray
    sharpe_paths: np.ndarray
    bh_sharpe_paths: np.ndarray
    bh_sharpe_real: float


def sharpe(returns: np.ndarray, axis: int = -1) -> np.ndarray:
    """Annualized sample-standard-deviation Sharpe; flat histories score zero."""
    std = np.std(returns, axis=axis, ddof=1)
    return np.divide(
        np.mean(returns, axis=axis), std, out=np.zeros_like(std), where=std > 1e-15
    ) * np.sqrt(TRADING_DAYS)


def _sma(close: np.ndarray, window: int) -> np.ndarray:
    total = np.cumsum(np.pad(close, ((0, 0), (1, 0))), axis=1)
    result = np.full_like(close, np.nan)
    if window <= close.shape[1]:
        result[:, window - 1 :] = (total[:, window:] - total[:, :-window]) / window
    return result


def _positions(close: np.ndarray, template_id: TemplateId, params: dict[str, float]) -> np.ndarray:
    if template_id == "ma_crossover":
        return (_sma(close, int(params["fast"])) > _sma(close, int(params["slow"]))).astype(np.int8)
    if template_id == "momentum":
        lookback = int(params["lookback"])
        pos = np.zeros_like(close, dtype=np.int8)
        if lookback < close.shape[1]:
            pos[:, lookback:] = close[:, lookback:] / close[:, :-lookback] - 1 > params["threshold"]
        return pos
    if template_id == "breakout":
        frame = pd.DataFrame(close.T)
        highs = frame.shift(1).rolling(int(params["entry_lookback"])).max().to_numpy().T
        lows = frame.shift(1).rolling(int(params["exit_lookback"])).min().to_numpy().T
        enter, exit = close > highs, close < lows
    elif template_id == "rsi_mean_reversion":
        period = int(params["period"])
        delta = np.diff(close, axis=1)
        gains, losses = np.maximum(delta, 0), np.maximum(-delta, 0)
        rsi = np.full_like(close, np.nan)
        if period < close.shape[1]:
            avg_gain, avg_loss = gains[:, :period].mean(axis=1), losses[:, :period].mean(axis=1)
            for t in range(period, close.shape[1]):
                if t > period:
                    avg_gain = (avg_gain * (period - 1) + gains[:, t - 1]) / period
                    avg_loss = (avg_loss * (period - 1) + losses[:, t - 1]) / period
                total = avg_gain + avg_loss
                rsi[:, t] = np.divide(
                    100 * avg_gain, total, out=np.full_like(total, 50.0), where=total > 1e-30
                )
        enter, exit = rsi < params["entry"], rsi > params["exit"]
    else:
        raise ValueError(f"Unknown template: {template_id}")
    # Most recent entry/exit event determines state; ties cannot arise for valid grids.
    clock = np.arange(close.shape[1])[None, :] + 1
    last_entry = np.maximum.accumulate(np.where(enter, clock, 0), axis=1)
    last_exit = np.maximum.accumulate(np.where(exit, clock, 0), axis=1)
    return (last_entry > last_exit).astype(np.int8)


def _strategy_returns(
    close: np.ndarray,
    market: np.ndarray,
    template_id: TemplateId,
    params: dict[str, float],
    cost: float,
) -> tuple[np.ndarray, np.ndarray]:
    position = _positions(close, template_id, params)
    previous = np.pad(position[:, :-1], ((0, 0), (1, 0)))
    returns = position[:, :-1] * market - cost * np.abs(position[:, :-1] - previous[:, :-1])
    return returns, position


def run_backtest(
    close0: float,
    r_real: np.ndarray,
    r_paths: np.ndarray,
    template_id: TemplateId,
    variants: list[dict[str, float]],
    costs_bps: float,
    progress: ProgressFn | None = None,
) -> BacktestResult:
    r_real = np.asarray(r_real, dtype=np.float64)
    r_paths = np.asarray(r_paths, dtype=np.float64)
    if (
        r_real.ndim != 1
        or r_paths.ndim != 2
        or r_paths.shape[1] != len(r_real)
        or len(r_real) < 2
        or not variants
    ):
        raise ValueError("Expected real (T,), paths (N,T), and at least one variant")
    if (
        close0 <= 0
        or not np.isfinite(close0)
        or not np.isfinite(r_real).all()
        or not np.isfinite(r_paths).all()
        or not 0 <= costs_bps <= 100
    ):
        raise ValueError("Prices, returns and costs must be finite and valid")
    if progress:
        progress(0.0)
    real_close = close0 * np.exp(np.pad(np.cumsum(r_real), (1, 0)))[None, :]
    real_market = np.expm1(r_real)[None, :]
    real_results = [
        _strategy_returns(real_close, real_market, template_id, p, costs_bps / 10000)
        for p in variants
    ]
    real_ret = np.column_stack([x[0][0] for x in real_results])
    real_sharpe = sharpe(real_ret, axis=0)
    selected = int(np.argmax(real_sharpe))
    n_paths, t = r_paths.shape
    path_sharpe = np.empty((n_paths, len(variants)))
    selected_ret = np.empty((n_paths, t))
    for start in range(0, n_paths, 100):
        stop = min(start + 100, n_paths)
        batch = r_paths[start:stop]
        close = close0 * np.exp(np.pad(np.cumsum(batch, axis=1), ((0, 0), (1, 0))))
        market = np.expm1(batch)
        for v, params in enumerate(variants):
            returns, _ = _strategy_returns(close, market, template_id, params, costs_bps / 10000)
            path_sharpe[start:stop, v] = sharpe(returns)
            if v == selected:
                selected_ret[start:stop] = returns
            if progress:
                progress((start + (stop - start) * (v + 1) / len(variants)) / max(n_paths, 1))
    bh_real = np.expm1(r_real)
    bh_paths = np.expm1(r_paths)
    bh_real[0] -= costs_bps / 10000
    bh_paths[:, 0] -= costs_bps / 10000
    return BacktestResult(
        variants,
        real_ret,
        real_sharpe,
        selected,
        real_results[selected][1][0],
        selected_ret,
        path_sharpe,
        sharpe(bh_paths),
        float(sharpe(bh_real)),
    )
