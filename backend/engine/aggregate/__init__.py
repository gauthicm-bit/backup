"""Contract §7 presentation payloads; statistics are supplied by engine metrics."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from engine.backtest.runner import BacktestResult
from engine.metrics.dsr import DSRResult
from engine.metrics.pbo import PBOResult
from engine.metrics.survival import SurvivalResult
from engine.realism.stylized_facts import RealismResult


def _clean(value: Any) -> Any:
    """Portable JSON with bounded precision; nonfinite cells are explicit nulls."""
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_clean(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(f"{value:.6g}") if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _json(value: Any) -> str:
    return json.dumps(_clean(value), separators=(",", ":"), allow_nan=False)


def _date_indices(length: int, maximum: int) -> np.ndarray:
    stride = max(1, int(np.ceil((length - 1) / (maximum - 1))))
    return np.unique(np.append(np.arange(0, length, stride), length - 1))


def realism_report(result: RealismResult, generator: str, n_paths: int) -> dict[str, Any]:
    """Convert the scalar-test and chart arrays without recomputing statistics."""

    def density(values: np.ndarray) -> list[float | None]:
        return [float(x) if np.isfinite(x) and x > 0 else None for x in values]

    return _clean(
        {
            "generator": generator,
            "n_paths": n_paths,
            "passed": sum(test.passed for test in result.tests),
            "total": len(result.tests),
            "tests": [
                {
                    "id": test.id,
                    "group": test.group,
                    "name": test.name,
                    "statistic": test.statistic,
                    "real": test.real,
                    "synthetic": {"p5": test.syn_p5, "p50": test.syn_p50, "p95": test.syn_p95},
                    "passed": test.passed,
                }
                for test in result.tests
            ],
            "return_distribution": {
                "x": result.density_x,
                "real_density": density(result.real_density),
                "syn_p5": density(result.syn_density_p5),
                "syn_p50": density(result.syn_density_p50),
                "syn_p95": density(result.syn_density_p95),
                "real_kurtosis": result.real_kurtosis,
                "syn_kurtosis_p50": result.syn_kurtosis_p50,
            },
            "vol_clustering": {
                "lags": result.acf_lags,
                "real": result.acf_sq_real,
                "syn_p5": result.acf_sq_p5,
                "syn_p50": result.acf_sq_p50,
                "syn_p95": result.acf_sq_p95,
            },
        }
    )


def build_charts(
    prices: pd.DataFrame,
    result: BacktestResult,
    pbo: PBOResult,
    dsr: DSRResult,
    survival: SurvivalResult,
    realism: RealismResult,
    rate: float,
    generator_type: str,
) -> dict[str, Any]:
    """Build every chart payload; use selected strategy returns for all equity."""
    dates = prices.index.strftime("%Y-%m-%d").tolist()
    selected = result.selected
    variant = result.variants[selected]
    n_paths = len(result.strat_ret_paths_selected)
    real_equity = np.concatenate([[1.0], np.cumprod(1 + result.strat_ret_real[:, selected])])
    path_equity = np.pad(
        np.cumprod(1 + result.strat_ret_paths_selected, axis=1),
        ((0, 0), (1, 0)),
        constant_values=1.0,
    )
    quantiles = np.percentile(path_equity, [5, 25, 50, 75, 95], axis=0)
    ordered = np.argsort(path_equity[:, -1], kind="stable")
    path_ids = ordered[np.floor(np.arange(0.05, 1.0, 0.1) * (n_paths - 1)).astype(int)]
    # Share the same stride for fan and paths, and enforce the size cap even for
    # unusually large equity values. 200 points leaves ample headroom below 50 KB.
    maximum = 200
    while True:
        indices = _date_indices(len(dates), maximum)
        sampled_dates = [dates[i] for i in indices]
        fan = _clean(
            {
                "dates": sampled_dates,
                **{
                    key: quantiles[i, indices]
                    for i, key in enumerate(["p5", "p25", "p50", "p75", "p95"])
                },
                "real": real_equity[indices],
                "real_rank": np.mean(path_equity[:, indices] <= real_equity[indices], axis=0),
                "n_histories": n_paths,
                "variant": variant,
            }
        )
        fan_paths = _clean(
            {
                "dates": sampled_dates,
                "paths": path_equity[path_ids][:, indices],
                "path_ids": path_ids,
            }
        )
        if max(len(_json(fan)), len(_json(fan_paths))) <= 50_000:
            break
        maximum = max(2, maximum // 2)
    selected_sharpes = result.sharpe_paths[:, selected]
    counts, bins = np.histogram(selected_sharpes, bins=40)
    pbo_counts, pbo_bins = np.histogram(np.clip(pbo.logits, -6, 6), bins=40, range=(-6, 6))
    points = np.unique(np.linspace(0, len(pbo.logits) - 1, min(1000, len(pbo.logits)), dtype=int))
    positions = result.position_real_selected
    changes = np.flatnonzero(positions != np.pad(positions[:-1], (1, 0)))
    signals = [
        {
            "date": dates[i],
            "side": "buy" if positions[i] else "sell",
            "price": float(prices.close.iloc[i]),
        }
        for i in changes
    ]
    ohlc = [
        {
            "date": dates[i],
            **{
                key: float(prices[key].iloc[i])
                for key in ["open", "high", "low", "close", "volume"]
            },
        }
        for i in range(len(prices))
    ]
    return _clean(
        {
            "fan": fan,
            "fan_paths": fan_paths,
            "sharpe": {
                "bins": bins,
                "counts": counts,
                "real_sharpe": result.sharpe_real[selected],
                "pct_beaten": np.mean(selected_sharpes > result.sharpe_real[selected]),
                "n_histories": n_paths,
            },
            "pbo": {
                "logit_bins": pbo_bins,
                "counts": pbo_counts,
                "pbo": pbo.pbo,
                "points": [{"is": pbo.is_sharpe[i], "oos": pbo.oos_sharpe[i]} for i in points],
                "slope": pbo.slope,
                "r2": pbo.r2,
                "n_splits": pbo.n_splits,
                "n_blocks": pbo.n_blocks,
            },
            "dsr": asdict(dsr),
            "survival": {**asdict(survival), "survival_rate": rate},
            "realism": realism_report(realism, generator_type, n_paths),
            "price": {"ohlc": ohlc, "signals": signals, "variant": variant},
        }
    )


def write_charts(directory: Path, charts: dict[str, Any]) -> None:
    """Persist chart files to the supplied charts directory with atomic renames."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in charts.items():
        serialized = _json(payload)
        if name != "price" and len(serialized.encode("utf-8")) > 50_000:
            raise ValueError(f"Chart {name} exceeds the contract's 50 KB limit")
        path = directory / f"{name}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(path)
