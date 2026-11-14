"""Contract §2.4, §5.4 and §5.6 grid validation."""

import pytest

from engine.backtest.templates import TEMPLATES, expand_grid
from engine.common import InvalidGrid


@pytest.mark.parametrize(
    "template_id,count",
    [("ma_crossover", 16), ("momentum", 12), ("rsi_mean_reversion", 8), ("breakout", 8)],
)
def test_default_grids(template_id, count):
    spec = TEMPLATES[template_id]
    grid = {p.name: p.default_values for p in spec.params}
    assert len(expand_grid(template_id, grid)) == count
    assert expand_grid(template_id, {k: list(reversed(v)) for k, v in grid.items()}) == expand_grid(
        template_id, grid
    )


@pytest.mark.parametrize(
    "grid",
    [
        {"fast": [5, 5], "slow": [50]},
        {"fast": [1, 5], "slow": [50]},
        {"fast": [5.5, 10], "slow": [50]},
        {"fast": [5, 10], "slow": [float("nan")]},
        {"fast": [5], "slow": [50]},
        {"fast": [50, 60], "slow": [10]},
        {"fast": [5, 10], "slow": [50], "extra": [1]},
    ],
)
def test_invalid_grids(grid):
    with pytest.raises(InvalidGrid):
        expand_grid("ma_crossover", grid)
