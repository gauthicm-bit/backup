"""Nifty OHLCV loader backed by a portable Parquet cache (contract §2.2)."""

import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from engine.common import MarketDataUnavailable

COLUMNS = ["open", "high", "low", "close", "volume"]


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame.columns = frame.columns.str.lower()
    frame = frame.loc[:, COLUMNS].astype("float64")
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    frame.index.name = "date"
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame = frame.loc[np.isfinite(frame["close"]) & (frame["close"] > 0)]
    if frame.empty:
        raise ValueError("Price source returned no valid close prices")
    return frame


def load_prices(symbol: str, start: date, end: date, *, cache_dir: Path) -> pd.DataFrame:
    """Read cached daily bars, downloading only when requested coverage is missing.

    Coverage metadata records the inclusive requested calendar range, so weekends
    and exchange holidays do not create perpetual cache misses.
    """
    if symbol != "^NSEI" or start > end:
        raise MarketDataUnavailable("Only ^NSEI with an ascending date range is supported")
    cache_path = Path(cache_dir) / f"{symbol}.parquet"
    cached = None
    try:
        if cache_path.exists():
            cached = pd.read_parquet(cache_path)
            covered_start = date.fromisoformat(
                cached.attrs.get("coverage_start", str(cached.index.min().date()))
            )
            covered_end = date.fromisoformat(
                cached.attrs.get("coverage_end", str(cached.index.max().date()))
            )
            cached.attrs.setdefault(
                "fetched_at",
                datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            )
            if covered_start <= start and covered_end >= end:
                result = _normalize(cached).loc[str(start) : str(end)].copy()
                if result.empty:
                    raise MarketDataUnavailable("No trading days in the requested date range")
                result.attrs["source"] = "cache"
                return result
        fetch_start = min(start, covered_start) if cached is not None else start
        fetch_end = max(end, covered_end) if cached is not None else end
        downloaded = yf.download(
            symbol,
            start=fetch_start.isoformat(),
            end=(fetch_end + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            progress=False,
            threads=False,
            timeout=20,
        )
        fresh = _normalize(downloaded)
        if cached is not None:
            fresh = _normalize(pd.concat([cached, fresh]))
        fresh.attrs = {
            "coverage_start": fetch_start.isoformat(),
            "coverage_end": fetch_end.isoformat(),
            "source": "yfinance",
            "symbol": symbol,
            "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Rename is atomic: workers never read a partially written Parquet file.
        handle, name = tempfile.mkstemp(
            prefix="nifty-", suffix=".parquet.tmp", dir=cache_path.parent
        )
        os.close(handle)
        temporary = Path(name)
        try:
            fresh.to_parquet(temporary)
            temporary.replace(cache_path)
        finally:
            temporary.unlink(missing_ok=True)
        result = fresh.loc[str(start) : str(end)].copy()
        if result.empty:
            raise ValueError("No trading days in requested range")
        return result
    except MarketDataUnavailable:
        raise
    except Exception as exc:
        raise MarketDataUnavailable(
            "Market prices unavailable; retry when the data provider is reachable"
        ) from exc


def log_returns(close: pd.Series | np.ndarray) -> np.ndarray:
    """Return float64 log(C[t]/C[t-1]); reject invalid input rather than emit NaN."""
    values = np.asarray(close, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("close must be a one-dimensional array of positive finite prices")
    return np.log(values[1:] / values[:-1])
