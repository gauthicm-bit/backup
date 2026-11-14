"""Prepare reproducible sliding return windows for offline challenger training.

Run from backend: python -m engine.data.windows --output models/nifty_windows.npz
No model is claimed trained by this dataset preparation utility.
"""

import argparse
from datetime import date
from pathlib import Path

import numpy as np

from engine.data.loader import load_prices, log_returns


def return_windows(returns: np.ndarray, window_days: int = 252) -> np.ndarray:
    """Return independent float64 copies of consecutive log-return windows."""
    values = np.asarray(returns, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("returns must be one-dimensional and finite")
    if window_days < 2 or values.size < window_days:
        raise ValueError("window_days must be at least 2 and fit within the history")
    return np.lib.stride_tricks.sliding_window_view(values, window_days).copy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2008, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--window-days", type=int, default=252)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/prices"))
    parser.add_argument("--output", type=Path, default=Path("models/nifty_windows.npz"))
    args = parser.parse_args()
    prices = load_prices("^NSEI", args.start, args.end, cache_dir=args.cache_dir)
    windows = return_windows(log_returns(prices.close), args.window_days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        windows=windows,
        dates=prices.index[args.window_days :].strftime("%Y-%m-%d").to_numpy(str),
    )
    print(f"Saved {len(windows)} windows of {args.window_days} days to {args.output}")


if __name__ == "__main__":
    main()
