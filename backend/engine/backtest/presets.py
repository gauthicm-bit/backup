"""Valid demo configurations; their verdicts always come from the real pipeline.

The slow-trend baseline currently also scores Luck; Gate 2 is recorded FAIL.
Names identify intended baselines and never override calculated results.
"""

PRESETS: dict[str, dict] = {
    "overfit": {
        "symbol": "^NSEI",
        "start": "2020-01-01",
        "end": "2025-12-31",
        "strategy": {
            "template": "momentum",
            "grid": {
                "lookback": [5, 10, 15, 20, 30, 45, 60, 90],
                "threshold": [-0.02, -0.01, 0, 0.01, 0.02, 0.03, 0.04, 0.05],
            },
        },
        "generator": {"type": "garch", "n_histories": 1000, "seed": 42},
        "costs_bps": 5,
        "reuse_cached": True,
    },
    "robust": {
        "symbol": "^NSEI",
        "start": "2010-01-01",
        "end": "2025-12-31",
        "strategy": {"template": "ma_crossover", "grid": {"fast": [20, 30], "slow": [150, 200]}},
        "generator": {"type": "garch", "n_histories": 1000, "seed": 42},
        "costs_bps": 5,
        "reuse_cached": True,
    },
}
