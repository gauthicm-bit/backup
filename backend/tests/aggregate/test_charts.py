"""Contract §7 chart invariants; use known returns rather than metric recomputation."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.aggregate import build_charts, write_charts
from engine.backtest.runner import BacktestResult
from engine.metrics.dsr import DSRResult
from engine.metrics.pbo import PBOResult
from engine.metrics.survival import SurvivalResult
from engine.realism.stylized_facts import run_realism


@pytest.fixture
def inputs():
    rng = np.random.default_rng(31)
    n, t = 100, 1200
    dates = pd.bdate_range("2010-01-01", periods=t + 1, name="date")
    prices = pd.DataFrame(
        {key: np.full(t + 1, 100.0) for key in ["open", "high", "low", "close", "volume"]},
        index=dates,
    )
    strategy = rng.normal(0.0002, 0.01, (n, t))
    real = strategy[0]
    paths_sharpe = np.column_stack([np.arange(n), np.arange(n) + 1])
    positions = np.zeros(t + 1, dtype=np.int8)
    positions[20:30] = 1
    result = BacktestResult(
        [{"fast": 5.0, "slow": 50.0}, {"fast": 10.0, "slow": 50.0}],
        np.column_stack([real, real]),
        np.array([1.0, 2.0]),
        1,
        positions,
        strategy,
        paths_sharpe,
        np.zeros(n),
        0.3,
    )
    pbo = PBOResult(
        0.5,
        np.linspace(-10, 10, 12870),
        np.linspace(-1, 2, 12870),
        np.linspace(-2, 1, 12870),
        0.5,
        0.8,
        12870,
        16,
    )
    dsr = DSRResult(2.0, 0.5, 1.5, 0.99, 2, 0.1, 3.0, t)
    survival = SurvivalResult(
        ["crash", "high_vol", "calm", "trend_up", "trend_down"],
        ["survival", "median_sharpe", "median_max_drawdown"],
        np.full((5, 3), np.nan),
        np.zeros(5, dtype=int),
        252,
    )
    realism = run_realism(real, strategy[:10])
    return prices, result, pbo, dsr, survival, realism, 0.7, "garch"


def test_chart_shapes_counts_and_units(inputs):
    charts = build_charts(*inputs)
    fan, paths = charts["fan"], charts["fan_paths"]
    assert 2 <= len(fan["dates"]) <= 500
    assert fan["dates"][0] == "2010-01-01"
    assert fan["dates"][-1] == inputs[0].index[-1].strftime("%Y-%m-%d")
    for key in ["p5", "p25", "p50", "p75", "p95", "real"]:
        assert len(fan[key]) == len(fan["dates"])
        assert fan[key][0] == 1.0
    assert paths["dates"] == fan["dates"]
    assert len(paths["paths"]) == len(paths["path_ids"]) == 10
    assert all(len(path) == len(fan["dates"]) and path[0] == 1 for path in paths["paths"])
    np.testing.assert_allclose(
        fan["real"][-1], np.prod(1 + inputs[1].strat_ret_real[:, 1]), rtol=1e-5
    )
    assert len(charts["sharpe"]["bins"]) == 41
    assert sum(charts["sharpe"]["counts"]) == 100
    assert charts["sharpe"]["pct_beaten"] == 0.98
    assert sum(charts["pbo"]["counts"]) == 12870
    assert len(charts["pbo"]["points"]) <= 1000
    assert set(charts["pbo"]["points"][0]) == {"is", "oos"}
    assert all(value is None for row in charts["survival"]["values"] for value in row)
    assert charts["price"]["signals"] == [
        {"date": inputs[0].index[20].strftime("%Y-%m-%d"), "side": "buy", "price": 100.0},
        {"date": inputs[0].index[30].strftime("%Y-%m-%d"), "side": "sell", "price": 100.0},
    ]


def test_json_size_determinism_and_write(inputs, tmp_path):
    charts = build_charts(*inputs)
    assert charts == build_charts(*inputs)
    write_charts(tmp_path, charts)
    for name, payload in charts.items():
        file = Path(tmp_path) / f"{name}.json"
        assert json.loads(file.read_text()) == payload
        if name != "price":
            assert file.stat().st_size <= 50_000
        assert "NaN" not in file.read_text()


def test_zero_density_becomes_null_for_log_axis(inputs):
    inputs[5].real_density[0] = 0
    charts = build_charts(*inputs)
    assert charts["realism"]["return_distribution"]["real_density"][0] is None


def test_payloads_validate_against_api_models(inputs):
    from app.schemas import api

    models = {
        "fan": api.FanChart,
        "fan_paths": api.FanPaths,
        "sharpe": api.SharpeChart,
        "pbo": api.PBOChart,
        "dsr": api.DSRChart,
        "survival": api.SurvivalChart,
        "realism": api.RealismReport,
        "price": api.PriceChart,
    }
    for name, payload in build_charts(*inputs).items():
        assert models[name].model_validate(payload)


def test_maximum_audit_dimensions_remain_within_payload_budget(inputs):
    prices, result, pbo, dsr, survival, realism, rate, generator = inputs
    n, t, v = 5000, 4500, 64
    dates = pd.bdate_range("2008-01-01", periods=t + 1, name="date")
    prices = pd.DataFrame(
        {key: np.full(t + 1, 100.0) for key in ["open", "high", "low", "close", "volume"]},
        index=dates,
    )
    result.strat_ret_paths_selected = np.full((n, t), 0.0002, dtype=np.float32)
    result.strat_ret_real = np.full((t, v), 0.0002)
    result.sharpe_paths = np.ones((n, v))
    result.sharpe_real = np.ones(v)
    result.variants = [{"fast": float(i + 2), "slow": 100.0} for i in range(v)]
    result.position_real_selected = np.zeros(t + 1, dtype=np.int8)
    charts = build_charts(prices, result, pbo, dsr, survival, realism, rate, generator)
    for name, payload in charts.items():
        if name != "price":
            assert len(json.dumps(payload, separators=(",", ":")).encode()) <= 50_000
    assert len(charts["fan_paths"]["paths"]) == 10
    assert all(len(path) == len(charts["fan"]["dates"]) for path in charts["fan_paths"]["paths"])
