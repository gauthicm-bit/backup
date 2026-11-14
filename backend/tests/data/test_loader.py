"""Price loader boundaries and units (API contract §2.2)."""

from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from engine.common import MarketDataUnavailable
from engine.data.loader import load_prices, log_returns


def prices():
    return pd.DataFrame(
        {
            "Open": [100, 102, 101],
            "High": [103, 104, 104],
            "Low": [99, 100, 100],
            "Close": [102, 101, 103],
            "Volume": [1000, 1200, 1100],
        },
        index=pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
    )


def test_log_returns_shape_and_units():
    close = np.array([100.0, 110.0, 99.0])
    result = log_returns(close)
    np.testing.assert_allclose(result, np.log(close[1:] / close[:-1]))
    assert result.shape == (2,)
    assert result.dtype == np.float64


@pytest.mark.parametrize("close", [[1, 0], [1, np.nan], [-1, 3], [[1, 2]]])
def test_invalid_close_rejected(close):
    with pytest.raises(ValueError):
        log_returns(np.array(close))


def test_cache_miss_writes_and_hit_skips_network(tmp_path):
    with patch("engine.data.loader.yf.download", return_value=prices()) as download:
        first = load_prices("^NSEI", date(2020, 1, 1), date(2020, 1, 3), cache_dir=tmp_path)
        assert download.call_count == 1
        assert first.attrs["source"] == "yfinance"
        assert first.attrs["fetched_at"].endswith("Z")
    assert (tmp_path / "^NSEI.parquet").exists()
    with patch("engine.data.loader.yf.download", side_effect=AssertionError("network on hit")):
        second = load_prices("^NSEI", date(2020, 1, 2), date(2020, 1, 3), cache_dir=tmp_path)
    assert len(second) == 2
    assert second.attrs["source"] == "cache"
    assert second.attrs["fetched_at"] == first.attrs["fetched_at"]
    assert first.index.name == "date"
    assert first.index.tz is None
    assert list(first.columns) == ["open", "high", "low", "close", "volume"]
    assert all(dtype == np.float64 for dtype in first.dtypes)


def test_outage_raises_domain_error(tmp_path):
    with patch("engine.data.loader.yf.download", side_effect=ConnectionError("offline")):
        with pytest.raises(MarketDataUnavailable):
            load_prices("^NSEI", date(2020, 1, 1), date(2020, 1, 3), cache_dir=tmp_path)


def test_empty_provider_result_raises(tmp_path):
    with patch("engine.data.loader.yf.download", return_value=pd.DataFrame()):
        with pytest.raises(MarketDataUnavailable):
            load_prices("^NSEI", date(2020, 1, 1), date(2020, 1, 3), cache_dir=tmp_path)


def test_legacy_cache_gets_file_timestamp_without_network(tmp_path):
    frame = prices()
    frame.columns = frame.columns.str.lower()
    frame.to_parquet(tmp_path / "^NSEI.parquet")
    with patch("engine.data.loader.yf.download", side_effect=AssertionError("cache hit")):
        loaded = load_prices("^NSEI", date(2020, 1, 1), date(2020, 1, 3), cache_dir=tmp_path)
    assert loaded.attrs["source"] == "cache"
    assert loaded.attrs["fetched_at"].endswith("Z")
