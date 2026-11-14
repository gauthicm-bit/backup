"""Strategy registry and deterministic grids (contract §2.4 / §5.4 / §5.6)."""

from dataclasses import dataclass
from itertools import product
from math import isfinite
from typing import Literal

from engine.common import InvalidGrid

TemplateId = Literal["ma_crossover", "momentum", "rsi_mean_reversion", "breakout"]


@dataclass(frozen=True)
class ParamSpec:
    name: str
    label: str
    type: Literal["int", "float"]
    min: float
    max: float
    step: float
    default_values: list[float]


@dataclass(frozen=True)
class Constraint:
    left: str
    op: Literal["<", "<="]
    right: str


@dataclass(frozen=True)
class TemplateSpec:
    id: TemplateId
    name: str
    description: str
    params: list[ParamSpec]
    constraints: list[Constraint]


TEMPLATES: dict[TemplateId, TemplateSpec] = {
    "ma_crossover": TemplateSpec(
        "ma_crossover",
        "Moving average crossover",
        "Long while the fast SMA exceeds the slow SMA.",
        [
            ParamSpec("fast", "Fast window", "int", 2, 100, 1, [5, 10, 20, 30]),
            ParamSpec("slow", "Slow window", "int", 10, 300, 1, [50, 100, 150, 200]),
        ],
        [Constraint("fast", "<", "slow")],
    ),
    "momentum": TemplateSpec(
        "momentum",
        "Momentum",
        "Long while trailing return exceeds the threshold.",
        [
            ParamSpec("lookback", "Lookback", "int", 5, 252, 1, [20, 60, 120, 252]),
            ParamSpec("threshold", "Threshold", "float", -0.05, 0.10, 0.005, [0, 0.02, 0.05]),
        ],
        [],
    ),
    "rsi_mean_reversion": TemplateSpec(
        "rsi_mean_reversion",
        "RSI mean reversion",
        "Enter below the RSI entry level; exit above the exit level.",
        [
            ParamSpec("period", "Period", "int", 2, 30, 1, [7, 14]),
            ParamSpec("entry", "Entry", "int", 5, 45, 1, [20, 30]),
            ParamSpec("exit", "Exit", "int", 50, 95, 1, [55, 70]),
        ],
        [Constraint("entry", "<", "exit")],
    ),
    "breakout": TemplateSpec(
        "breakout",
        "Breakout",
        "Enter above prior highs; exit below prior lows.",
        [
            ParamSpec("entry_lookback", "Entry lookback", "int", 10, 252, 1, [20, 55, 100, 200]),
            ParamSpec("exit_lookback", "Exit lookback", "int", 5, 126, 1, [10, 20]),
        ],
        [Constraint("exit_lookback", "<=", "entry_lookback")],
    ),
}


def expand_grid(template_id: TemplateId, grid: dict[str, list[float]]) -> list[dict[str, float]]:
    if template_id not in TEMPLATES:
        raise InvalidGrid(f"Unknown template: {template_id}")
    spec = TEMPLATES[template_id]
    if set(grid) != {p.name for p in spec.params}:
        raise InvalidGrid("Grid keys must exactly match the template parameter names")
    for param in spec.params:
        values = grid[param.name]
        if not isinstance(values, list) or not 1 <= len(values) <= 10:
            raise InvalidGrid(f"{param.name} requires 1–10 values")
        if any(
            isinstance(x, bool) or not isinstance(x, (float, int)) or not isfinite(x)
            for x in values
        ):
            raise InvalidGrid(f"{param.name} requires finite numeric values")
        if len(set(values)) != len(values):
            raise InvalidGrid(f"{param.name} values must be unique")
        if any(
            not param.min <= x <= param.max or (param.type == "int" and x != int(x)) for x in values
        ):
            raise InvalidGrid(
                f"{param.name} must be within [{param.min}, {param.max}] and match its type"
            )
    variants = []
    for values in product(*(sorted(grid[p.name]) for p in spec.params)):
        variant = dict(zip((p.name for p in spec.params), values, strict=True))
        if all(
            variant[c.left] < variant[c.right]
            if c.op == "<"
            else variant[c.left] <= variant[c.right]
            for c in spec.constraints
        ):
            variants.append(variant)
    if not 2 <= len(variants) <= 64:
        raise InvalidGrid("Grid must produce 2–64 variants after parameter constraints")
    return variants
