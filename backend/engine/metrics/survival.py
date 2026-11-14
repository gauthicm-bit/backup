"""Non-overlapping regime windows (contract §2.5)."""

from dataclasses import dataclass

import numpy as np
from engine.backtest.runner import sharpe


@dataclass
class SurvivalResult:
    regimes: list[str]
    metrics: list[str]
    values: np.ndarray
    n_windows: np.ndarray
    window_days: int


def compute_survival(
    r_paths: np.ndarray, strat_ret_paths_selected: np.ndarray, window_days: int = 252
) -> SurvivalResult:
    market = np.asarray(r_paths, dtype=float)
    strategy = np.asarray(strat_ret_paths_selected, dtype=float)
    if (
        market.ndim != 2
        or market.shape != strategy.shape
        or window_days < 2
        or not np.isfinite(market).all()
        or not np.isfinite(strategy).all()
        or np.any(strategy <= -1)
    ):
        raise ValueError("Survival requires aligned finite (N,T) arrays and simple returns > -1")
    count = market.shape[1] // window_days
    values, counts = np.full((5, 3), np.nan), np.zeros(5, dtype=int)
    if count:
        m = market[:, : count * window_days].reshape(-1, window_days)
        s = strategy[:, : count * window_days].reshape(-1, window_days)
        equity = np.exp(np.pad(np.cumsum(m, axis=1), ((0, 0), (1, 0))))
        drawdown = np.min(equity / np.maximum.accumulate(equity, axis=1) - 1, axis=1)
        vol = np.std(m, axis=1, ddof=1)
        low, high = np.quantile(vol, [1 / 3, 2 / 3])
        gain = np.expm1(m.sum(axis=1))
        crash = drawdown <= -0.2
        masks = [crash, vol >= high, vol <= low, gain >= 0.15, (gain <= -0.1) & ~crash]
        sr = sharpe(s)
        strat_eq = np.exp(np.pad(np.cumsum(np.log1p(s), axis=1), ((0, 0), (1, 0))))
        strat_dd = np.min(strat_eq / np.maximum.accumulate(strat_eq, axis=1) - 1, axis=1)
        for i, mask in enumerate(masks):
            counts[i] = int(mask.sum())
            if counts[i]:
                values[i] = [np.mean(sr[mask] > 0), np.median(sr[mask]), np.median(strat_dd[mask])]
    return SurvivalResult(
        ["crash", "high_vol", "calm", "trend_up", "trend_down"],
        ["survival", "median_sharpe", "median_max_drawdown"],
        values,
        counts,
        window_days,
    )


def compute_survival_rate(sharpe_paths_selected: np.ndarray, bh_sharpe_paths: np.ndarray) -> float:
    selected, bh = np.asarray(sharpe_paths_selected), np.asarray(bh_sharpe_paths)
    if (
        selected.ndim != 1
        or selected.shape != bh.shape
        or not len(selected)
        or not np.isfinite(selected).all()
        or not np.isfinite(bh).all()
    ):
        raise ValueError("Survival rate requires nonempty aligned finite Sharpe arrays")
    return float(np.mean(selected > bh))
