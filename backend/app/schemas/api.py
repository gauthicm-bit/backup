"""Wire schemas transcribed from API contract 1.0.0, §§1,5,7,8."""

from __future__ import annotations
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field

Symbol = Literal["^NSEI"]
AuditStatus = Literal["queued", "running", "done", "error", "cancelled"]
Verdict = Literal["skill", "luck", "inconclusive"]
Stage = Literal["fetch", "simulate", "backtest", "metrics"]
GeneratorType = Literal["garch", "timegan", "diffusion"]
TemplateId = Literal["ma_crossover", "momentum", "rsi_mean_reversion", "breakout"]
NHistories = Literal[100, 500, 1000, 5000]
PresetId = Literal["overfit", "robust"]
Regime = Literal["crash", "high_vol", "calm", "trend_up", "trend_down"]
SurvivalMetric = Literal["survival", "median_sharpe", "median_max_drawdown"]
RealismTestId = Literal[
    "excess_kurtosis",
    "hill_tail_index",
    "acf_returns",
    "acf_abs_returns",
    "acf_sq_returns",
    "leverage",
    "kurtosis_5d",
    "kurtosis_20d",
]
RealismGroup = Literal[
    "fat_tails", "no_autocorrelation", "vol_clustering", "leverage", "aggregational_gaussianity"
]


class Health(BaseModel):
    status: Literal["ok", "degraded"]  # degraded if redis or db is down
    redis: Literal["ok", "down"]
    db: Literal["ok", "down"]
    job_mode: Literal["rq", "inprocess"]
    contract_version: str  # "1.0.0" — C shows a warning on mismatch


class OHLCRow(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None


class PriceResponse(BaseModel):
    symbol: Symbol
    start: date
    end: date
    source: Literal["cache", "yfinance"]
    fetched_at: datetime
    ohlc: list[OHLCRow]  # ascending, trading days only


class ParamInfo(BaseModel):
    name: str
    label: str
    type: Literal["int", "float"]
    min: float
    max: float
    step: float
    default_values: list[float]


class ConstraintInfo(BaseModel):
    left: str
    op: Literal["<", "<="]
    right: str


class TemplateInfo(BaseModel):
    id: TemplateId
    name: str
    description: str
    params: list[ParamInfo]  # in grid-expansion order
    constraints: list[ConstraintInfo]  # C evaluates these to show the live variant count
    default_grid: dict[str, list[float]]
    default_n_variants: int


class TrainedOn(BaseModel):
    symbol: Symbol
    start: date
    end: date


class GeneratorInfo(BaseModel):
    id: GeneratorType
    name: str
    description: str
    trained: bool  # weights exist (garch: always true, fit per audit)
    available: bool  # selectable in the builder; false -> UI shows "coming soon"
    realism_passed: bool | None  # null = report not built yet
    trained_on: TrainedOn | None


class StrategySpec(BaseModel):
    template: TemplateId
    grid: dict[str, list[float]]  # every param of the template must be present


class GeneratorSpec(BaseModel):
    type: GeneratorType = "garch"
    n_histories: NHistories = 1000
    seed: int = Field(42, ge=0, le=2_147_483_647)


class CreateAuditRequest(BaseModel):
    symbol: Symbol = "^NSEI"
    start: date
    end: date
    strategy: StrategySpec
    generator: GeneratorSpec = GeneratorSpec()
    costs_bps: float = Field(5, ge=0, le=100)
    reuse_cached: bool = True


class CreateAuditResponse(BaseModel):
    audit_id: str
    status: AuditStatus  # "queued" normally; "done" when cached
    cached: bool


class Progress(BaseModel):
    stage: Stage
    pct: int  # 0–100 within the stage
    message: str


class SelectedVariant(BaseModel):
    index: int
    params: dict[str, float]
    real_sharpe: float


class AuditDerived(BaseModel):
    n_trials: int  # == len(variants)
    variants: list[dict[str, float]]
    selected_variant: SelectedVariant | None  # null until backtest stage done
    config_hash: str
    versions: dict[str, str]  # python, numpy, pandas, arch, vectorbt, torch?, app


class AuditMetrics(BaseModel):
    pbo: float
    dsr_prob: float
    survival_rate: float
    n_trials: int


class ThresholdsOut(BaseModel):
    pbo_skill_max: float
    dsr_skill_min: float
    survival_skill_min: float
    pbo_luck_min: float
    dsr_luck_max: float


class ErrorInfo(BaseModel):
    code: str
    message: str


class AuditDetail(BaseModel):
    id: str
    status: AuditStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    config: CreateAuditRequest
    derived: AuditDerived
    verdict: Verdict | None  # set only when status == "done"
    headline: str | None
    metrics: AuditMetrics | None
    thresholds: ThresholdsOut  # tiles show "threshold used"
    progress: Progress | None  # last known, while queued/running
    error: ErrorInfo | None  # set only when status == "error"


class AuditListItem(BaseModel):
    id: str
    status: AuditStatus
    verdict: Verdict | None
    created_at: datetime
    finished_at: datetime | None
    symbol: Symbol
    start: date
    end: date
    template: TemplateId
    generator: GeneratorType
    n_histories: int
    n_trials: int
    metrics: AuditMetrics | None


class AuditList(BaseModel):
    items: list[AuditListItem]
    total: int
    limit: int
    offset: int


class CancelResponse(BaseModel):
    id: str
    status: Literal["cancelled"]


class Preset(BaseModel):
    id: PresetId
    name: str
    description: str
    config: CreateAuditRequest
    cached_audit_id: str | None  # set once warm-presets has run


class FanChart(BaseModel):
    dates: list[date]  # ≤ 500, ascending, always includes first and last date
    p5: list[float]
    p25: list[float]
    p50: list[float]
    p75: list[float]
    p95: list[float]
    real: list[float]  # selected variant on real history
    real_rank: list[float]  # 0–1: share of histories with equity <= real on that date (hover)
    n_histories: int
    variant: dict[str, float]  # selected variant params


class FanPaths(BaseModel):
    dates: list[date]  # same as FanChart.dates
    paths: list[list[float]]  # exactly 10 × len(dates)
    path_ids: list[int]  # the 10 path ids: final-equity ranks at 5%,15%,…,95%


class SharpeChart(BaseModel):
    bins: list[float]  # bin EDGES, len = len(counts) + 1, 40 bins
    counts: list[int]  # sum == n_histories
    real_sharpe: float  # selected variant on real
    pct_beaten: float  # 0–1: share of histories with Sharpe > real_sharpe
    n_histories: int


class PBOPoint(BaseModel):
    is_: float = Field(alias="is")  # serialize by_alias -> JSON key "is"
    oos: float


class PBOChart(BaseModel):
    logit_bins: list[float]  # edges, len = len(counts) + 1, 40 bins, logits clipped to [-6, 6]
    counts: list[int]  # sum == n_splits
    pbo: float
    points: list[PBOPoint]  # ≤ 1000, even sample of splits (seed 0), annualized Sharpe
    slope: float
    r2: float  # fitted on ALL splits
    n_splits: int
    n_blocks: int


class DSRChart(BaseModel):
    raw_sharpe: float
    deflated_sharpe: float
    sr0: float  # annualized
    dsr_prob: float
    n_trials: int
    skew: float
    kurtosis: float
    sample_length: int


class SurvivalChart(BaseModel):
    regimes: list[Regime]  # 5, enum order
    metrics: list[SurvivalMetric]  # 3, enum order
    values: list[list[float | None]]  # [regime][metric]; null if n_windows == 0
    n_windows: list[int]  # per regime
    window_days: int  # 252
    survival_rate: float  # headline, repeated for the tab header


class Band(BaseModel):
    p5: float
    p50: float
    p95: float


class RealismTestOut(BaseModel):
    id: RealismTestId
    group: RealismGroup
    name: str
    statistic: str
    real: float
    synthetic: Band
    passed: bool


class ReturnDistribution(BaseModel):
    x: list[float]  # ≤ 200
    real_density: list[float | None]  # null where 0 (log y-axis)
    syn_p5: list[float | None]
    syn_p50: list[float | None]
    syn_p95: list[float | None]
    real_kurtosis: float
    syn_kurtosis_p50: float


class VolClustering(BaseModel):
    lags: list[int]  # 1..50
    real: list[float]
    syn_p5: list[float]
    syn_p50: list[float]
    syn_p95: list[float]


class RealismReport(BaseModel):
    generator: GeneratorType
    n_paths: int
    passed: int
    total: int  # e.g. 7 / 8
    tests: list[RealismTestOut]  # 8, RealismTestId order
    return_distribution: ReturnDistribution
    vol_clustering: VolClustering


class Signal(BaseModel):
    date: date
    side: Literal["buy", "sell"]
    price: float


class PriceChart(BaseModel):
    ohlc: list[OHLCRow]  # real history of the audit
    signals: list[Signal]  # selected variant's position changes
    variant: dict[str, float]


class FieldError(BaseModel):
    loc: list[str | int]
    msg: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
