"""Deflated Sharpe Ratio: Bailey and Lopez de Prado (2014), contract §2.5."""

from dataclasses import dataclass

import numpy as np
from scipy.special import ndtr, ndtri


@dataclass
class DSRResult:
    raw_sharpe: float
    sr0: float
    deflated_sharpe: float
    dsr_prob: float
    n_trials: int
    skew: float
    kurtosis: float
    sample_length: int


def expected_max_sharpe(n_trials: int, variance: float) -> float:
    if n_trials < 2 or variance < 0:
        raise ValueError("Expected maximum needs at least two trials and nonnegative variance")
    gamma = float(np.euler_gamma)
    return float(
        np.sqrt(variance)
        * ((1 - gamma) * ndtri(1 - 1 / n_trials) + gamma * ndtri(1 - 1 / (n_trials * np.e)))
    )


def deflated_probability(
    sr: float, sr0: float, sample_length: int, skew: float, kurtosis: float
) -> float:
    """Paper eq. 2; SR and benchmark are daily, kurtosis is Pearson."""
    denominator = max(1 - skew * sr + (kurtosis - 1) / 4 * sr * sr, 1e-15)
    return float(ndtr((sr - sr0) * np.sqrt(sample_length - 1) / np.sqrt(denominator)))


def compute_dsr(strat_ret_real: np.ndarray, selected: int) -> DSRResult:
    returns = np.asarray(strat_ret_real, dtype=float)
    if (
        returns.ndim != 2
        or returns.shape[1] < 2
        or len(returns) < 3
        or not 0 <= selected < returns.shape[1]
        or not np.isfinite(returns).all()
    ):
        raise ValueError("DSR requires finite (T,V), T>=3, V>=2, and a valid selected index")
    std = returns.std(axis=0, ddof=1)
    daily = np.divide(returns.mean(axis=0), std, out=np.zeros_like(std), where=std > 1e-15)
    n_trials = returns.shape[1]
    sr0 = expected_max_sharpe(n_trials, float(np.var(daily, ddof=1)))
    r = returns[:, selected]
    centered = r - r.mean()
    m2 = float(np.mean(centered**2))
    skew = float(np.mean(centered**3) / m2**1.5) if m2 > 1e-30 else 0.0
    kurt = float(np.mean(centered**4) / m2**2) if m2 > 1e-30 else 3.0
    sr = float(daily[selected])
    probability = deflated_probability(sr, sr0, len(r), skew, kurt)
    scale = np.sqrt(252)
    return DSRResult(
        sr * scale, sr0 * scale, (sr - sr0) * scale, probability, n_trials, skew, kurt, len(r)
    )
