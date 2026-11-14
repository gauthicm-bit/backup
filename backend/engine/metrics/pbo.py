"""Combinatorially symmetric cross-validation (contract §2.5)."""

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from engine.common import ProgressFn


@dataclass
class PBOResult:
    pbo: float
    logits: np.ndarray
    is_sharpe: np.ndarray
    oos_sharpe: np.ndarray
    slope: float
    r2: float
    n_splits: int
    n_blocks: int


def compute_pbo(
    strat_ret_real: np.ndarray, n_blocks: int = 16, progress: ProgressFn | None = None
) -> PBOResult:
    returns = np.asarray(strat_ret_real, dtype=float)
    if (
        returns.ndim != 2
        or returns.shape[1] < 2
        or n_blocks < 2
        or n_blocks % 2
        or len(returns) < n_blocks * 2
        or not np.isfinite(returns).all()
    ):
        raise ValueError("PBO requires finite (T,V), V>=2, even blocks, and >=2 rows/block")
    returns = returns[len(returns) % n_blocks :]
    blocks = returns.reshape(n_blocks, -1, returns.shape[1])
    sums = blocks.sum(axis=1)
    squares = (blocks * blocks).sum(axis=1)
    choices = np.array(list(combinations(range(n_blocks), n_blocks // 2)))
    sample_n = blocks.shape[1] * (n_blocks // 2)
    total_sum, total_square = sums.sum(axis=0), squares.sum(axis=0)
    logits, is_scores, oos_scores = [], [], []
    if progress:
        progress(0.0)

    def scores(s: np.ndarray, ss: np.ndarray) -> np.ndarray:
        variance = np.maximum((ss - s * s / sample_n) / (sample_n - 1), 0.0)
        return np.divide(
            s / sample_n, np.sqrt(variance), out=np.zeros_like(s), where=variance > 1e-30
        )

    for start in range(0, len(choices), 256):
        selection = choices[start : start + 256]
        is_sum = sums[selection].sum(axis=1)
        is_square = squares[selection].sum(axis=1)
        ins = scores(is_sum, is_square)
        oos = scores(total_sum - is_sum, total_square - is_square)
        winner = ins.argmax(axis=1)
        row = np.arange(len(selection))
        chosen = oos[row, winner]
        # Stable ordinal ties retain contract ranks in 1..V; lowest index ranks first.
        ranks = (oos < chosen[:, None]).sum(axis=1) + (
            (oos == chosen[:, None]) & (np.arange(returns.shape[1])[None, :] <= winner[:, None])
        ).sum(axis=1)
        omega = ranks / (returns.shape[1] + 1)
        logits.extend(np.log(omega / (1 - omega)))
        is_scores.extend(ins[row, winner] * np.sqrt(252))
        oos_scores.extend(chosen * np.sqrt(252))
        if progress:
            progress(min(start + 256, len(choices)) / len(choices))
    logits = np.asarray(logits)
    ins, oos = np.asarray(is_scores), np.asarray(oos_scores)
    x, y = ins - ins.mean(), oos - oos.mean()
    xx, yy = float(x @ x), float(y @ y)
    slope = float(x @ y / xx) if xx > 1e-25 else 0.0
    r2 = float(np.clip((x @ y) ** 2 / (xx * yy), 0, 1)) if xx * yy > 1e-25 else 0.0
    return PBOResult(
        float(np.mean(logits <= 0)), logits, ins, oos, slope, r2, len(choices), n_blocks
    )
