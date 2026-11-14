"""Contract §2.5 verdict rules and exact headline templates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    pbo_skill_max: float = 0.25
    dsr_skill_min: float = 0.95
    survival_skill_min: float = 0.60
    pbo_luck_min: float = 0.50
    dsr_luck_max: float = 0.50


DEFAULT_THRESHOLDS = Thresholds()


@dataclass
class VerdictResult:
    verdict: str
    headline: str


def decide_verdict(
    pbo: float,
    dsr_prob: float,
    survival_rate: float,
    n_histories: int,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> VerdictResult:
    prefix = f"In {n_histories:,} alternate histories this strategy beat buy-and-hold"
    percent = round(survival_rate * 100)
    if pbo >= thresholds.pbo_luck_min or dsr_prob < thresholds.dsr_luck_max:
        return VerdictResult(
            "luck", f"{prefix} only {percent}% of the time. Its backtest result is likely luck."
        )
    if (
        pbo < thresholds.pbo_skill_max
        and dsr_prob >= thresholds.dsr_skill_min
        and survival_rate >= thresholds.survival_skill_min
    ):
        return VerdictResult(
            "skill", f"{prefix} {percent}% of the time. Its edge holds up beyond luck."
        )
    return VerdictResult("inconclusive", f"{prefix} {percent}% of the time. The evidence is mixed.")
