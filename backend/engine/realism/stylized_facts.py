"""Eight stylized-fact diagnostics and chart arrays (contract §2.5)."""

from dataclasses import dataclass

import numpy as np

from engine.common import ProgressFn


@dataclass
class RealismTest:
    id: str
    group: str
    name: str
    statistic: str
    real: float
    syn_p5: float
    syn_p50: float
    syn_p95: float
    passed: bool


@dataclass
class RealismResult:
    tests: list[RealismTest]
    density_x: np.ndarray
    real_density: np.ndarray
    syn_density_p5: np.ndarray
    syn_density_p50: np.ndarray
    syn_density_p95: np.ndarray
    real_kurtosis: float
    syn_kurtosis_p50: float
    acf_lags: np.ndarray
    acf_sq_real: np.ndarray
    acf_sq_p5: np.ndarray
    acf_sq_p50: np.ndarray
    acf_sq_p95: np.ndarray


def _kurtosis(x: np.ndarray) -> float:
    centered = x - np.mean(x)
    variance = np.mean(centered**2)
    return float(np.mean(centered**4) / variance**2 - 3) if variance > 1e-30 else 0.0


def _acf(x: np.ndarray, count: int) -> np.ndarray:
    centered = x - np.mean(x)
    norm = np.dot(centered, centered)
    return np.array(
        [
            np.dot(centered[:-lag], centered[lag:]) / norm if norm > 1e-30 and lag < len(x) else 0.0
            for lag in range(1, count + 1)
        ]
    )


def _correlation(x: np.ndarray, y: np.ndarray) -> float:
    x = x - x.mean()
    y = y - y.mean()
    denom = np.linalg.norm(x) * np.linalg.norm(y)
    return float(np.dot(x, y) / denom) if denom > 1e-30 else 0.0


def _stats(x: np.ndarray) -> np.ndarray:
    tail = np.sort(np.abs(x))
    count = max(1, int(len(x) * 0.05))
    threshold = tail[-count - 1]
    hill_denom = float(np.mean(np.log(tail[-count:] / threshold))) if threshold > 0 else 0.0
    hill = 1 / hill_denom if hill_denom > 1e-15 else 0.0
    aggregate = [x[: len(x) // k * k].reshape(-1, k).sum(axis=1) for k in (5, 20)]
    return np.array(
        [
            _kurtosis(x),
            hill,
            np.mean(np.abs(_acf(x, 10))),
            np.mean(_acf(np.abs(x), 50)),
            np.mean(_acf(x * x, 50)),
            np.mean([_correlation(x[:-k], np.abs(x[k:])) for k in range(1, 21)]),
            *[_kurtosis(a) for a in aggregate],
        ]
    )


_DEFINITIONS = [
    ("excess_kurtosis", "fat_tails", "Daily fat tails", "Excess kurtosis of daily returns"),
    ("hill_tail_index", "fat_tails", "Tail index", "Hill estimator, top 5% absolute returns"),
    ("acf_returns", "no_autocorrelation", "Return autocorrelation", "Mean absolute ACF, lags 1–10"),
    (
        "acf_abs_returns",
        "vol_clustering",
        "Absolute-return persistence",
        "Mean ACF of absolute returns, lags 1–50",
    ),
    (
        "acf_sq_returns",
        "vol_clustering",
        "Squared-return persistence",
        "Mean ACF of squared returns, lags 1–50",
    ),
    (
        "leverage",
        "leverage",
        "Leverage effect",
        "Mean return / future absolute-return correlation, lags 1–20",
    ),
    (
        "kurtosis_5d",
        "aggregational_gaussianity",
        "Five-day tails",
        "Excess kurtosis of 5-day summed returns",
    ),
    (
        "kurtosis_20d",
        "aggregational_gaussianity",
        "Twenty-day tails",
        "Excess kurtosis of 20-day summed returns",
    ),
]


def run_realism(
    r_real: np.ndarray, r_paths: np.ndarray, progress: ProgressFn | None = None
) -> RealismResult:
    r_real = np.asarray(r_real, dtype=float)
    r_paths = np.asarray(r_paths, dtype=float)
    if (
        r_real.ndim != 1
        or len(r_real) < 60
        or r_paths.ndim != 2
        or r_paths.shape[1] != len(r_real)
        or len(r_paths) == 0
        or not np.isfinite(r_real).all()
        or not np.isfinite(r_paths).all()
    ):
        raise ValueError("Realism requires finite real (T,) and paths (N,T), with T >= 60")
    if progress:
        progress(0.0)
    minimum = min(float(r_real.min()), float(r_paths.min()))
    maximum = max(float(r_real.max()), float(r_paths.max()))
    if maximum - minimum < 1e-12:
        minimum, maximum = minimum - 1e-5, maximum + 1e-5
    edges = np.linspace(minimum, maximum, 201)
    real_density = np.histogram(r_real, bins=edges, density=True)[0]
    statistics, densities, acfs = [], [], []
    for i, path in enumerate(r_paths):
        statistics.append(_stats(path))
        densities.append(np.histogram(path, bins=edges, density=True)[0])
        acfs.append(_acf(path * path, 50))
        if progress and (i % 10 == 0 or i == len(r_paths) - 1):
            progress((i + 1) / len(r_paths))
    bands = np.percentile(statistics, [5, 50, 95], axis=0)
    real_stats = _stats(r_real)
    tests = [
        RealismTest(
            *definition,
            float(real_stats[i]),
            *map(float, bands[:, i]),
            bool(bands[0, i] <= real_stats[i] <= bands[2, i]),
        )
        for i, definition in enumerate(_DEFINITIONS)
    ]
    density_bands = np.percentile(densities, [5, 50, 95], axis=0)
    acf_bands = np.percentile(acfs, [5, 50, 95], axis=0)
    return RealismResult(
        tests,
        (edges[:-1] + edges[1:]) / 2,
        real_density,
        *density_bands,
        float(real_stats[0] + 3),
        float(bands[1, 0] + 3),
        np.arange(1, 51),
        _acf(r_real * r_real, 50),
        *acf_bands,
    )
