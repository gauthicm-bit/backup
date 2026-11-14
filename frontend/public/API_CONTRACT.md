# Multiverse v2 — API Master Contract

**Contract version:** `1.0.0` · **Source spec:** *Multiverse — Full-Stack Spec v2.2* (Nov 14, 2026) + `WORKFLOW` diagram
**Status:** binding for Person A, Person B, Person C and every AI agent working for them.

This file is the single source of truth for every boundary between roles:

| Boundary | Between | Section |
|---|---|---|
| Shared vocabulary (enums, units, IDs, dates) | everyone | §1 |
| Engine interfaces (Python, in-process) | A ↔ B | §2 |
| On-disk storage + DB | A ↔ B (A writes) | §3 |
| Job pipeline, Redis keys, progress | A ↔ B, A ↔ C | §4 |
| REST API `/api/v1` | A ↔ C | §5 |
| SSE progress stream | A ↔ C | §6 |
| Chart payloads | A/B ↔ C | §7 |
| Errors | A ↔ C | §8 |
| Change control | everyone | §9 |
| Decisions this contract made where the spec was silent | everyone | §10 |

> **Rule zero.** If your code disagrees with this file, your code is wrong. If this file is wrong, change it through §9 **before** changing code.

---

## 0. Ownership (from the WORKFLOW diagram)

| Stage | Folder | Owner |
|---|---|---|
| 1 · Data | `backend/engine/data/` | **Person A** |
| 2 · Generators (GARCH, TimeGAN challenger) | `backend/engine/generators/` | **Person A** |
| 3 · Backtest | `backend/engine/backtest/` | **Person B** |
| 4 · Metrics (realism, PBO, DSR, survival, verdict) | `backend/engine/metrics/`, `backend/engine/realism/` | **Person B** |
| 5 · Backend (FastAPI, Redis, RQ worker, chart payloads, storage) | `backend/app/`, `backend/engine/aggregate/` | **Person A** |
| 6 · Frontend | `frontend/` | **Person C** |

Data flow (left → right):

```
Data ──real returns──▶ Generators ──N histories──▶ Backtest ──returns + Sharpes──▶ Metrics ──scores + verdict──▶ Backend ──REST + SSE──▶ Frontend
  └──────────── real Nifty returns: grid search (→ Backtest) + realism benchmark (→ Metrics) ────────────┘
```

---

## 1. Shared vocabulary

### 1.1 Enums (exact strings; lowercase; never translate)

```python
# backend/app/schemas/common.py  — Person A owns the file, values are contract
from typing import Literal

Symbol         = Literal["^NSEI"]                                   # only symbol in v2
AuditStatus    = Literal["queued", "running", "done", "error", "cancelled"]
Verdict        = Literal["skill", "luck", "inconclusive"]
Stage          = Literal["fetch", "simulate", "backtest", "metrics"] # order is fixed
GeneratorType  = Literal["garch", "timegan", "diffusion"]
TemplateId     = Literal["ma_crossover", "momentum", "rsi_mean_reversion", "breakout"]
NHistories     = Literal[100, 500, 1000, 5000]
PresetId       = Literal["overfit", "robust"]
Regime         = Literal["crash", "high_vol", "calm", "trend_up", "trend_down"]   # this order
SurvivalMetric = Literal["survival", "median_sharpe", "median_max_drawdown"]      # this order
ChartName      = Literal["fan", "fan_paths", "sharpe", "pbo", "dsr", "survival", "realism", "price"]
RealismTestId  = Literal["excess_kurtosis", "hill_tail_index", "acf_returns",
                         "acf_abs_returns", "acf_sq_returns", "leverage",
                         "kurtosis_5d", "kurtosis_20d"]
RealismGroup   = Literal["fat_tails", "no_autocorrelation", "vol_clustering",
                         "leverage", "aggregational_gaussianity"]
```

Status lifecycle (no other transitions are legal):

```
queued ──▶ running ──▶ done
   │          ├──────▶ error
   └──────────┴──────▶ cancelled
```

### 1.2 Units and formats

| Thing | Rule |
|---|---|
| Ratios (`pbo`, `dsr_prob`, `survival_rate`, `pct_beaten`, `real_rank`, regime `survival`, drawdowns) | **fractions 0–1** in every payload. The frontend formats `%`. Drawdowns are **negative** fractions (`-0.18`). |
| Sharpe ratios in payloads | **annualized**, `mean / std × √252`, risk-free rate = 0. |
| Sharpe ratios inside DSR/PBO maths | daily (non-annualized); only the payload is annualized. |
| Equity series | growth of 1.0 (starts at exactly `1.0`). Frontend may display as ₹ growth of ₹1. |
| Returns stored on disk | real/synthetic market returns = **log** returns; strategy returns = **simple** returns after costs. |
| Dates | `"YYYY-MM-DD"` strings (trading days, IST market dates, no time part). |
| Timestamps | ISO-8601 UTC with `Z`: `"2026-11-14T09:00:00Z"`. |
| Audit IDs | `"aud_" + ULID` (26 chars Crockford base32), e.g. `aud_01JCX8Q6T3W9K2M4N5P7R8S0TV`. |
| NaN / ±inf | never serialized. Replace with `null`. Fields that can be `null` say so. |
| JSON keys | `snake_case` everywhere, including in the frontend's generated types. |
| Variant columns | `v00`, `v01`, … (zero-padded 2 digits; max 64 variants). Index = position in `derived.variants`. |
| Path ids | integers `0 … n_histories-1`; parquet columns `p0000 … p4999`. |

### 1.3 Array conventions (engine)

For a request with real close prices on `T+1` trading days:

| Name | Shape | Meaning |
|---|---|---|
| `dates` | `(T+1,)` | trading days of the real history |
| `close_real` | `(T+1,)` | real closes |
| `r_real` | `(T,)` | `ln(close[t] / close[t-1])`, aligned to `dates[1:]` |
| `r_paths` | `(n_paths, T)` | synthetic log returns, same alignment as `r_real` |
| synthetic closes (built inside backtest) | `(n_paths, T+1)` | `close_real[0] * exp(cumsum(r_paths))` with `close_real[0]` prepended |

Synthetic histories have **close only** — no open/high/low/volume. Every strategy template therefore uses **close prices only** (see D-03).

---

## 2. Engine interfaces (Python, in-process) — A ↔ B

All engine packages are **pure**: no FastAPI, no Redis, no DB, no file writes (exceptions: `engine/data` reads/writes its Parquet cache; generators `save()`/`load()` weights). The worker (Person A) does all I/O.

Every long-running engine function accepts `progress: Callable[[float], None] | None = None` and calls it with a fraction `0.0–1.0` at least every ~2 seconds. It must also raise `Cancelled` (from `engine.common`) if `progress` raises it — the worker uses that to cancel.

### 2.1 `engine/common.py` (Person A creates at hour 0; both may add, never rename)

```python
class EngineError(Exception):
    code: str = "internal_error"          # maps to §8 error codes
class MarketDataUnavailable(EngineError): code = "market_data_unavailable"
class InvalidGrid(EngineError):           code = "invalid_grid"
class GeneratorNotTrained(EngineError):   code = "generator_not_trained"
class Cancelled(Exception): ...

ProgressFn = Callable[[float], None]
TRADING_DAYS = 252
```

### 2.2 Data — **Person A provides**, B consumes

```python
# engine/data/loader.py
def load_prices(symbol: str, start: date, end: date, *, cache_dir: Path) -> pd.DataFrame:
    """Daily OHLCV from the Parquet cache; yfinance only on a cache miss.
    Returns: index = DatetimeIndex named "date" (tz-naive, ascending, unique);
             columns = open, high, low, close, volume  (float64; volume may be NaN);
             no NaN in close. Raises MarketDataUnavailable."""

def log_returns(close: pd.Series | np.ndarray) -> np.ndarray:
    """r_t = ln(C_t / C_{t-1}); shape (T,) for T+1 closes."""
```

### 2.3 Generators — **Person A provides**, B consumes paths

```python
# engine/generators/base.py
class Generator(ABC):
    type: ClassVar[GeneratorType]
    def fit(self, returns: np.ndarray) -> "Generator": ...            # returns: (T,) log returns
    def sample(self, n_paths: int, length: int, seed: int) -> np.ndarray: ...
        # -> (n_paths, length) float64 log returns; identical output for identical
        #    (fitted state, n_paths, length, seed). No NaN.
    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path) -> "Generator": ...

def get_generator(type: GeneratorType) -> Generator: ...   # raises GeneratorNotTrained
def is_available(type: GeneratorType) -> bool: ...         # garch: always True
```

- `garch` = GJR-GARCH(1,1), Student-t (or skewed-t) innovations via `arch`; **fit on the audit's own `r_real`** every audit.
- `timegan` / `diffusion` = trained offline; `load()` at worker start; `sample()` chains windows to reach `length`.

### 2.4 Backtest — **Person B provides**, A consumes

```python
# engine/backtest/templates.py
@dataclass(frozen=True)
class ParamSpec:
    name: str; label: str; type: Literal["int", "float"]
    min: float; max: float; step: float; default_values: list[float]

@dataclass(frozen=True)
class Constraint:
    left: str; op: Literal["<", "<="]; right: str          # e.g. fast < slow

@dataclass(frozen=True)
class TemplateSpec:
    id: TemplateId; name: str; description: str
    params: list[ParamSpec]; constraints: list[Constraint]

TEMPLATES: dict[TemplateId, TemplateSpec]

def expand_grid(template_id: TemplateId, grid: dict[str, list[float]]) -> list[dict[str, float]]:
    """Cartesian product in ParamSpec order, values ascending, constraint-violating
    combos dropped. Deterministic order. Raises InvalidGrid (see §5.6 rules)."""
```

```python
# engine/backtest/runner.py
@dataclass
class BacktestResult:
    variants: list[dict[str, float]]          # == expand_grid output
    strat_ret_real: np.ndarray                # (T, V) simple daily returns after costs
    sharpe_real: np.ndarray                   # (V,) annualized
    selected: int                             # argmax(sharpe_real); ties -> lowest index
    position_real_selected: np.ndarray        # (T+1,) int8 in {0,1}; position held after close t
    strat_ret_paths_selected: np.ndarray      # (n_paths, T) selected variant on every path
    sharpe_paths: np.ndarray                  # (n_paths, V) annualized
    bh_sharpe_paths: np.ndarray               # (n_paths,) buy-and-hold Sharpe per path
    bh_sharpe_real: float

def run_backtest(close0: float, r_real: np.ndarray, r_paths: np.ndarray,
                 template_id: TemplateId, variants: list[dict[str, float]],
                 costs_bps: float, progress: ProgressFn | None = None) -> BacktestResult: ...
```

Backtest rules (binding):
- **Long/flat only**, position ∈ {0, 1} (D-04).
- Signal computed at close *t* → position held over *t → t+1*. No look-ahead.
- Costs: `costs_bps / 10_000 × |Δposition|` deducted from that day's return.
- Warm-up days (indicator not defined yet) → position 0.
- "Selected variant" = best real-history Sharpe (the grid-search winner, per the dashed "grid search" arrow). Fan, Sharpe histogram, Survival, DSR and the price signals all use it.

### 2.5 Metrics — **Person B provides**, A consumes

```python
# engine/metrics/pbo.py
@dataclass
class PBOResult:
    pbo: float                    # share of logits <= 0
    logits: np.ndarray            # (n_splits,)
    is_sharpe: np.ndarray         # (n_splits,) annualized, best-IS variant, in-sample
    oos_sharpe: np.ndarray        # (n_splits,) same variant, out-of-sample
    slope: float; r2: float       # OLS oos ~ is over all splits
    n_splits: int; n_blocks: int  # 12870, 16
def compute_pbo(strat_ret_real: np.ndarray, n_blocks: int = 16,
                progress: ProgressFn | None = None) -> PBOResult: ...
```
CSCV: drop the first `T mod 16` rows; 16 equal blocks; all C(16,8)=12,870 splits; performance = Sharpe; relative OOS rank ω = rank/(V+1) with rank ∈ 1..V (so the logit is always finite); λ = ln(ω/(1−ω)).

```python
# engine/metrics/dsr.py
@dataclass
class DSRResult:
    raw_sharpe: float          # annualized, selected variant on real
    sr0: float                 # annualized expected max Sharpe of N noise trials
    deflated_sharpe: float     # annualized (SR - SR0)
    dsr_prob: float            # Φ(...) per spec formula, 0..1
    n_trials: int              # V
    skew: float                # γ3 of selected variant daily returns
    kurtosis: float            # γ4 raw (Pearson; normal = 3)
    sample_length: int         # T
def compute_dsr(strat_ret_real: np.ndarray, selected: int) -> DSRResult: ...
```
`V[SR_n]` = variance across variants of daily Sharpe on the real history. Requires `n_trials ≥ 2`.

```python
# engine/metrics/survival.py
@dataclass
class SurvivalResult:
    regimes: list[Regime]               # always all 5, in enum order
    metrics: list[SurvivalMetric]       # always all 3, in enum order
    values: np.ndarray                  # (5, 3); NaN where a regime has 0 windows
    n_windows: np.ndarray               # (5,) int
    window_days: int                    # 252
def compute_survival(r_paths: np.ndarray, strat_ret_paths_selected: np.ndarray,
                     window_days: int = 252) -> SurvivalResult: ...
def compute_survival_rate(sharpe_paths_selected: np.ndarray,
                          bh_sharpe_paths: np.ndarray) -> float:
    """Headline survival rate = share of synthetic histories where the selected
    variant's Sharpe (after costs) > buy-and-hold Sharpe on the same history. (D-06)"""
```
Regime rules (defaults; windows = non-overlapping 252-day blocks of each path, remainder dropped; index stats from `r_paths`):

| Regime | Rule |
|---|---|
| `crash` | index max drawdown within window ≥ 20% |
| `high_vol` | realized vol in top third of **all** windows (all paths) |
| `calm` | realized vol in bottom third of all windows |
| `trend_up` | window index return ≥ +15% |
| `trend_down` | window index return ≤ −10% **and not** `crash` |

A window may sit in several regimes (except crash/trend_down). Metric columns per regime: `survival` = share of windows where strategy Sharpe after costs > 0; `median_sharpe` (annualized); `median_max_drawdown` (negative fraction).

```python
# engine/realism/stylized_facts.py
@dataclass
class RealismTest:
    id: RealismTestId; group: RealismGroup; name: str; statistic: str
    real: float; syn_p5: float; syn_p50: float; syn_p95: float
    passed: bool                       # syn_p5 <= real <= syn_p95
@dataclass
class RealismResult:
    tests: list[RealismTest]           # all 8, in RealismTestId order
    density_x: np.ndarray              # (K,) return grid, K <= 200
    real_density: np.ndarray           # (K,)
    syn_density_p5: np.ndarray; syn_density_p50: np.ndarray; syn_density_p95: np.ndarray
    real_kurtosis: float; syn_kurtosis_p50: float
    acf_lags: np.ndarray               # (50,) = 1..50
    acf_sq_real: np.ndarray            # (50,)
    acf_sq_p5: np.ndarray; acf_sq_p50: np.ndarray; acf_sq_p95: np.ndarray
def run_realism(r_real: np.ndarray, r_paths: np.ndarray,
                progress: ProgressFn | None = None) -> RealismResult: ...
```
Test definitions (one scalar statistic each, so "real inside 5–95% band" is well defined):

| id | group | statistic |
|---|---|---|
| `excess_kurtosis` | fat_tails | excess kurtosis of daily returns |
| `hill_tail_index` | fat_tails | Hill estimator, top 5% absolute returns |
| `acf_returns` | no_autocorrelation | mean \|ACF\| of returns, lags 1–10 |
| `acf_abs_returns` | vol_clustering | mean ACF of \|r\|, lags 1–50 |
| `acf_sq_returns` | vol_clustering | mean ACF of r², lags 1–50 |
| `leverage` | leverage | mean corr(r_t, \|r_{t+k}\|), k = 1–20 (expected < 0) |
| `kurtosis_5d` | aggregational_gaussianity | excess kurtosis of 5-day summed returns |
| `kurtosis_20d` | aggregational_gaussianity | excess kurtosis of 20-day summed returns |

```python
# engine/metrics/verdict.py
@dataclass(frozen=True)
class Thresholds:
    pbo_skill_max: float = 0.25      # skill needs pbo <  this
    dsr_skill_min: float = 0.95      # skill needs dsr >= this
    survival_skill_min: float = 0.60 # skill needs survival >= this
    pbo_luck_min: float = 0.50       # luck if pbo >= this
    dsr_luck_max: float = 0.50       # luck if dsr <  this
DEFAULT_THRESHOLDS = Thresholds()

@dataclass
class VerdictResult:
    verdict: Verdict
    headline: str
def decide_verdict(pbo: float, dsr_prob: float, survival_rate: float,
                   n_histories: int, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> VerdictResult: ...
```
Order: Luck test first, then Skill, else Inconclusive. Headline templates (N with thousands separator, s = round(survival_rate×100)):
- luck: `In {N} alternate histories this strategy beat buy-and-hold only {s}% of the time. Its backtest result is likely luck.`
- skill: `In {N} alternate histories this strategy beat buy-and-hold {s}% of the time. Its edge holds up beyond luck.`
- inconclusive: `In {N} alternate histories this strategy beat buy-and-hold {s}% of the time. The evidence is mixed.`

### 2.6 Aggregate — Person A, internal

`engine/aggregate/` turns `BacktestResult`, `PBOResult`, `DSRResult`, `SurvivalResult`, `RealismResult`, `VerdictResult` into the JSON payloads of §7. B never builds JSON; A never re-computes a metric.

### 2.7 Presets — Person B defines the strategies, Person A serves and caches them

```python
# engine/backtest/presets.py  (Person B)
PRESETS: dict[PresetId, dict]   # each value is a valid CreateAuditRequest body (§5.6)
```
`overfit` must come out **luck**; `robust` must come out **skill** (Gate 2).

---

## 3. Storage

### 3.1 Files — `${DATA_DIR}/` (default `backend/data/`)

```
data/
├── cache/prices/^NSEI.parquet          # A: full cached history, refreshed on miss
├── generators/{type}/weights.*          # A: trained deep models
├── generators/{type}/realism.json       # A: §7.7 payload for /generators/{id}/realism
└── audits/{audit_id}/
    ├── config.json                      # CreateAuditRequest + derived (§5.7 AuditDerived)
    ├── paths.parquet                    # rows = T (col "date" + p0000..), float32 log returns
    ├── returns_real.parquet             # rows = T (col "date" + v00..), float64 strategy returns
    ├── sharpe_matrix.parquet            # rows = n_paths (col "path" + v00..), float64 annualized
    └── charts/{fan,fan_paths,sharpe,pbo,dsr,survival,realism,price}.json
```
Only the worker (A) writes these. Deleting an audit deletes the folder and the DB row.

### 3.2 Database (SQLModel; SQLite dev, Postgres deploy) — Person A

| Table | Columns |
|---|---|
| `audit` | `id` PK str · `status` AuditStatus · `config` JSON · `config_hash` str (sha256 of canonical request JSON minus `reuse_cached`) indexed · `verdict` nullable · `headline` nullable · `pbo` · `dsr_prob` · `survival_rate` (nullable floats) · `n_trials` int · `selected_variant` JSON nullable · `error_code` · `error_message` nullable · `created_at` · `started_at` · `finished_at` nullable |
| `generator_model` | `id` · `type` · `trained_on` JSON {symbol,start,end} · `weights_path` · `realism_passed` bool nullable · `created_at` |
| `price_cache` | `symbol` · `start` · `end` · `parquet_path` · `fetched_at` |

---

## 4. Job pipeline, Redis, progress

### 4.1 Settings (`pydantic-settings`, `.env`)

| Var | Default | Used by |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/multiverse.db` | A |
| `REDIS_URL` | `redis://localhost:6379/0` | A |
| `DATA_DIR` | `./data` | A |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | A (CORS) |
| `JOB_MODE` | `rq` (`inprocess` = FastAPI BackgroundTasks fallback) | A |
| `MAX_HISTORIES` | `5000` | A |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | C |

### 4.2 Pipeline (`app/worker/run_audit.py`, Person A) — one RQ job per audit

| # | SSE stage | Work | Calls |
|---|---|---|---|
| 1 | `fetch` | load prices for `[start, end]`, compute `r_real` | `load_prices`, `log_returns` (A) |
| 2 | `simulate` | fit/load generator, sample `n_histories × T`, write `paths.parquet` | `Generator` (A) |
| 3 | `backtest` | expand grid, run all variants on real + every path, write parquet | `expand_grid`, `run_backtest` (B) |
| 4 | `metrics` | PBO, DSR, survival, survival rate, realism, verdict, then aggregate charts + write DB row | B's metrics, A's aggregate |

The spec's steps 5 (Aggregate) and 6 (Verdict) report under SSE stage `metrics` (the UI stepper has four stages, FR-06).

### 4.3 Redis

| Key / name | Type | Content |
|---|---|---|
| queue `audits` | RQ queue | job id = audit id, timeout 15 min |
| `audit:{id}` | pub/sub channel | JSON `{"event": <SSE event name>, "data": <SSE data>}` (§6) |
| `audit:{id}:last` | string, TTL 24 h | last published message (for late SSE subscribers) |
| `audit:{id}:cancel` | string `"1"`, TTL 1 h | set by `DELETE`; worker's progress callback raises `Cancelled` |
| `prices:{symbol}:{start}:{end}` | string, TTL 1 h | optional hot cache of `/market/prices` JSON |

### 4.4 Caching and presets
- `POST /audits` with `reuse_cached: true` and a `done` audit with the same `config_hash` → return that audit's id with `cached: true` (no new job).
- Both presets are precomputed at deploy (`uv run python -m app.cli warm-presets`) so the demo always hits the cache.

---

## 5. REST API — base `/api/v1`

General rules:
- JSON only, `Content-Type: application/json; charset=utf-8`, gzip for responses > 1 KB.
- CORS: only `FRONTEND_ORIGIN`. No auth in v2.
- Swagger at `/docs`, schema at `/openapi.json` (both at the server root).
- Non-job endpoints ≤ 300 ms; chart payloads ≤ 50 KB uncompressed (except `price`, see §7.8).
- Every 4xx/5xx body is the §8 error shape. FastAPI's default 422 body is replaced.
- Response models are declared on every route (`response_model=`) so OpenAPI → TypeScript is complete.

### 5.1 Endpoint index

| Method | Path | Success | Response model | FR |
|---|---|---|---|---|
| GET | `/health` | 200 | `Health` | — |
| GET | `/market/prices?symbol=^NSEI&start=&end=` | 200 | `PriceResponse` | FR-01 |
| GET | `/strategies/templates` | 200 | `list[TemplateInfo]` | FR-02, FR-03 |
| GET | `/generators` | 200 | `list[GeneratorInfo]` | FR-04 |
| GET | `/generators/{id}/realism` | 200 | `RealismReport` | FR-13 |
| GET | `/presets` | 200 | `list[Preset]` | FR-16 |
| POST | `/audits` | **202** | `CreateAuditResponse` | FR-05 |
| GET | `/audits?limit=&offset=&status=` | 200 | `AuditList` | FR-15 |
| GET | `/audits/{id}` | 200 | `AuditDetail` | FR-07 |
| GET | `/audits/{id}/events` | 200 `text/event-stream` | §6 | FR-06 |
| DELETE | `/audits/{id}` | 200 (cancelled) / 204 (deleted) | `CancelResponse` / empty | FR-05 |
| GET | `/audits/{id}/charts/fan` | 200 | `FanChart` | FR-08 |
| GET | `/audits/{id}/charts/fan/paths` | 200 | `FanPaths` | FR-08 toggle |
| GET | `/audits/{id}/charts/sharpe` | 200 | `SharpeChart` | FR-09 |
| GET | `/audits/{id}/charts/pbo` | 200 | `PBOChart` | FR-10 |
| GET | `/audits/{id}/charts/dsr` | 200 | `DSRChart` | FR-11 |
| GET | `/audits/{id}/charts/survival` | 200 | `SurvivalChart` | FR-12 |
| GET | `/audits/{id}/charts/realism` | 200 | `RealismReport` | FR-13 (audit tab) |
| GET | `/audits/{id}/charts/price` | 200 | `PriceChart` | price chart w/ signals |

All `/audits/{id}/charts/*` return **404 `audit_not_found`** if the id is unknown and **409 `chart_not_ready`** if `status != "done"`.

### 5.2 `GET /health`
```python
class Health(BaseModel):
    status: Literal["ok", "degraded"]       # degraded if redis or db is down
    redis: Literal["ok", "down"]
    db: Literal["ok", "down"]
    job_mode: Literal["rq", "inprocess"]
    contract_version: str                   # "1.0.0" — C shows a warning on mismatch
```

### 5.3 `GET /market/prices`
Query: `symbol` (Symbol, required), `start`, `end` (dates, required, `start < end`).
```python
class OHLCRow(BaseModel):
    date: date; open: float; high: float; low: float; close: float
    volume: float | None
class PriceResponse(BaseModel):
    symbol: Symbol; start: date; end: date
    source: Literal["cache", "yfinance"]
    fetched_at: datetime
    ohlc: list[OHLCRow]                      # ascending, trading days only
```
Errors: 422 `invalid_date_range`, 503 `market_data_unavailable`.

### 5.4 `GET /strategies/templates`
```python
class ParamInfo(BaseModel):
    name: str; label: str; type: Literal["int", "float"]
    min: float; max: float; step: float; default_values: list[float]
class ConstraintInfo(BaseModel):
    left: str; op: Literal["<", "<="]; right: str
class TemplateInfo(BaseModel):
    id: TemplateId; name: str; description: str
    params: list[ParamInfo]                  # in grid-expansion order
    constraints: list[ConstraintInfo]        # C evaluates these to show the live variant count
    default_grid: dict[str, list[float]]
    default_n_variants: int
```
Template catalogue (B implements, A serves, C renders):

| id | params (type, min–max, step) | constraint | default grid → variants |
|---|---|---|---|
| `ma_crossover` | `fast` int 2–100 step 1 · `slow` int 10–300 step 1 | `fast < slow` | fast [5,10,20,30] × slow [50,100,150,200] → 16 |
| `momentum` | `lookback` int 5–252 step 1 · `threshold` float −0.05–0.10 step 0.005 | — | lookback [20,60,120,252] × threshold [0,0.02,0.05] → 12 |
| `rsi_mean_reversion` | `period` int 2–30 · `entry` int 5–45 · `exit` int 50–95 | `entry < exit` | period [7,14] × entry [20,30] × exit [55,70] → 8 |
| `breakout` | `entry_lookback` int 10–252 · `exit_lookback` int 5–126 | `exit_lookback <= entry_lookback` | entry [20,55,100,200] × exit [10,20] → 8 |

Semantics (long/flat, close only): MA — long while SMA(fast) > SMA(slow). Momentum — long while trailing `lookback`-day return > `threshold`. RSI — go long when RSI(period) < `entry`, exit when RSI > `exit`. Breakout — go long when close > max of previous `entry_lookback` closes, exit when close < min of previous `exit_lookback` closes.

### 5.5 `GET /generators`, `GET /generators/{id}/realism`
```python
class TrainedOn(BaseModel):
    symbol: Symbol; start: date; end: date
class GeneratorInfo(BaseModel):
    id: GeneratorType; name: str; description: str
    trained: bool                 # weights exist (garch: always true, fit per audit)
    available: bool               # selectable in the builder; false -> UI shows "coming soon"
    realism_passed: bool | None   # null = report not built yet
    trained_on: TrainedOn | None
```
`/generators/{id}/realism` returns `RealismReport` (§7.7) computed on `^NSEI 2010-01-01 … 2025-12-31`, 500 paths, seed 42. Errors: 404 `generator_not_found`, 409 `realism_not_ready`.

### 5.6 `POST /audits`
```python
class StrategySpec(BaseModel):
    template: TemplateId
    grid: dict[str, list[float]]            # every param of the template must be present

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
    status: AuditStatus                     # "queued" normally; "done" when cached
    cached: bool
```
Validation (server is authoritative; C mirrors it in Zod):

| Rule | Error code (422) |
|---|---|
| `start ≥ 2008-01-01`, `end ≤ today`, `end − start ≥ 3 years` | `invalid_date_range` |
| grid keys == template param names exactly | `invalid_grid` |
| each param: 1–10 unique values, inside `[min, max]`, ints are whole numbers | `invalid_grid` |
| variants after constraints: **2 ≤ V ≤ 64** | `invalid_grid` |
| `generator.type` available | `generator_not_trained` |
| `n_histories ≤ MAX_HISTORIES` | `too_many_histories` |
| request body ≤ 16 KB | 413 `request_too_large` |

Example request (from spec):
```json
{
  "symbol": "^NSEI", "start": "2010-01-01", "end": "2025-12-31",
  "strategy": { "template": "ma_crossover",
                "grid": { "fast": [5, 10, 20, 30], "slow": [50, 100, 150, 200] } },
  "generator": { "type": "garch", "n_histories": 1000, "seed": 42 },
  "costs_bps": 5
}
```
Response `202`, header `Location: /api/v1/audits/{id}`:
```json
{ "audit_id": "aud_01JCX8Q6T3W9K2M4N5P7R8S0TV", "status": "queued", "cached": false }
```

### 5.7 `GET /audits/{id}`
```python
class Progress(BaseModel):
    stage: Stage; pct: int                  # 0–100 within the stage
    message: str

class SelectedVariant(BaseModel):
    index: int; params: dict[str, float]; real_sharpe: float

class AuditDerived(BaseModel):
    n_trials: int                           # == len(variants)
    variants: list[dict[str, float]]
    selected_variant: SelectedVariant | None   # null until backtest stage done
    config_hash: str
    versions: dict[str, str]                # python, numpy, pandas, arch, vectorbt, torch?, app

class AuditMetrics(BaseModel):
    pbo: float; dsr_prob: float; survival_rate: float; n_trials: int

class ThresholdsOut(BaseModel):
    pbo_skill_max: float; dsr_skill_min: float; survival_skill_min: float
    pbo_luck_min: float; dsr_luck_max: float

class ErrorInfo(BaseModel):
    code: str; message: str

class AuditDetail(BaseModel):
    id: str
    status: AuditStatus
    created_at: datetime; started_at: datetime | None; finished_at: datetime | None
    config: CreateAuditRequest
    derived: AuditDerived
    verdict: Verdict | None                 # set only when status == "done"
    headline: str | None
    metrics: AuditMetrics | None
    thresholds: ThresholdsOut               # tiles show "threshold used"
    progress: Progress | None               # last known, while queued/running
    error: ErrorInfo | None                 # set only when status == "error"
```
Example (done):
```json
{
  "id": "aud_01JCX8Q6T3W9K2M4N5P7R8S0TV", "status": "done",
  "created_at": "2026-11-14T09:00:00Z", "started_at": "2026-11-14T09:00:01Z", "finished_at": "2026-11-14T09:01:32Z",
  "config": { "symbol": "^NSEI", "start": "2010-01-01", "end": "2025-12-31",
              "strategy": { "template": "ma_crossover", "grid": { "fast": [5,10,20,30], "slow": [50,100,150,200] } },
              "generator": { "type": "garch", "n_histories": 1000, "seed": 42 },
              "costs_bps": 5, "reuse_cached": true },
  "derived": { "n_trials": 16, "variants": [{ "fast": 5, "slow": 50 }],
               "selected_variant": { "index": 6, "params": { "fast": 10, "slow": 150 }, "real_sharpe": 0.84 },
               "config_hash": "9f2c…", "versions": { "python": "3.12.6", "arch": "7.2.0", "vectorbt": "0.26.2", "app": "2.2.0" } },
  "verdict": "luck",
  "headline": "In 1,000 alternate histories this strategy beat buy-and-hold only 31% of the time. Its backtest result is likely luck.",
  "metrics": { "pbo": 0.62, "dsr_prob": 0.41, "survival_rate": 0.31, "n_trials": 16 },
  "thresholds": { "pbo_skill_max": 0.25, "dsr_skill_min": 0.95, "survival_skill_min": 0.6, "pbo_luck_min": 0.5, "dsr_luck_max": 0.5 },
  "progress": null, "error": null
}
```
(`variants` truncated in the example; the real response lists all 16. Values illustrative.)

### 5.8 `GET /audits`
Query: `limit` 1–100 (default 50), `offset` ≥ 0 (default 0), `status` (optional AuditStatus). Sorted `created_at` desc.
```python
class AuditListItem(BaseModel):
    id: str; status: AuditStatus; verdict: Verdict | None
    created_at: datetime; finished_at: datetime | None
    symbol: Symbol; start: date; end: date
    template: TemplateId; generator: GeneratorType
    n_histories: int; n_trials: int
    metrics: AuditMetrics | None
class AuditList(BaseModel):
    items: list[AuditListItem]; total: int; limit: int; offset: int
```

### 5.9 `DELETE /audits/{id}`
- `queued` / `running` → sets cancel flag, status → `cancelled`, publishes `cancelled` event, returns **200** `CancelResponse {id, status: "cancelled"}`.
- `done` / `error` / `cancelled` → deletes row + folder, returns **204** (no body).
- **Retry** of a failed audit = C re-POSTs `config` from `AuditDetail` (no separate endpoint).

```python
class CancelResponse(BaseModel):
    id: str; status: Literal["cancelled"]
```

### 5.10 `GET /presets`
```python
class Preset(BaseModel):
    id: PresetId; name: str; description: str
    config: CreateAuditRequest
    cached_audit_id: str | None             # set once warm-presets has run
```

---

## 6. SSE — `GET /audits/{id}/events`

`Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Browser uses native `EventSource` (no credentials).

| `event:` | `data:` JSON | When |
|---|---|---|
| `progress` | `{"stage": Stage, "pct": 0-100, "message": str, "ts": timestamp}` | at stage start (pct 0), at least every 2 s, at stage end (pct 100) |
| `done` | `{"audit_id": str, "verdict": Verdict}` | once; server then closes |
| `error` | `{"code": str, "message": str}` | once; server then closes |
| `cancelled` | `{"audit_id": str}` | once; server then closes |
| *(comment)* `: ping` | — | every 15 s |

Wire example:
```
event: progress
data: {"stage":"backtest","pct":40,"message":"Backtesting 16 variants on 1,000 histories","ts":"2026-11-14T09:00:40Z"}

event: done
data: {"audit_id":"aud_01JCX8Q6T3W9K2M4N5P7R8S0TV","verdict":"luck"}
```
Behaviour on connect (A): if status is `done`/`error`/`cancelled`, send that terminal event immediately and close. Otherwise first replay `audit:{id}:last`, then relay the pub/sub channel. Stages always arrive in order `fetch → simulate → backtest → metrics`; a later stage implies earlier ones are 100%.

Client rules (C): on terminal event, close the `EventSource` and `invalidateQueries(["audit", id])`. On network error, `EventSource` auto-reconnects; after 3 failures, fall back to polling `GET /audits/{id}` every 2 s.

---

## 7. Chart payloads — `GET /audits/{id}/charts/{name}`

Built by A's `engine/aggregate` from B's results; stored as `charts/{name}.json`; served as-is. All arrays in one payload have the lengths stated. ≤ 50 KB each (except `price`).

### 7.1 `fan` — FanChart
```python
class FanChart(BaseModel):
    dates: list[date]            # ≤ 500, ascending, always includes first and last date
    p5: list[float]; p25: list[float]; p50: list[float]; p75: list[float]; p95: list[float]
    real: list[float]            # selected variant on real history
    real_rank: list[float]       # 0–1: share of histories with equity <= real on that date (hover)
    n_histories: int
    variant: dict[str, float]    # selected variant params
```
Equity = growth of 1.0 of the selected variant after costs; all series are `1.0` at `dates[0]`. Downsample by even stride.

### 7.2 `fan_paths` — FanPaths (`/charts/fan/paths`, loaded on toggle)
```python
class FanPaths(BaseModel):
    dates: list[date]            # same as FanChart.dates
    paths: list[list[float]]     # exactly 10 × len(dates)
    path_ids: list[int]          # the 10 path ids: final-equity ranks at 5%,15%,…,95%
```

### 7.3 `sharpe` — SharpeChart
```python
class SharpeChart(BaseModel):
    bins: list[float]            # bin EDGES, len = len(counts) + 1, 40 bins
    counts: list[int]            # sum == n_histories
    real_sharpe: float           # selected variant on real
    pct_beaten: float            # 0–1: share of histories with Sharpe > real_sharpe
    n_histories: int
```

### 7.4 `pbo` — PBOChart
```python
class PBOPoint(BaseModel):
    is_: float = Field(alias="is")   # serialize by_alias -> JSON key "is"
    oos: float
class PBOChart(BaseModel):
    logit_bins: list[float]      # edges, len = len(counts) + 1, 40 bins, logits clipped to [-6, 6]
    counts: list[int]            # sum == n_splits
    pbo: float
    points: list[PBOPoint]       # ≤ 1000, even sample of splits (seed 0), annualized Sharpe
    slope: float; r2: float      # fitted on ALL splits
    n_splits: int; n_blocks: int
```

### 7.5 `dsr` — DSRChart
```python
class DSRChart(BaseModel):
    raw_sharpe: float; deflated_sharpe: float; sr0: float   # annualized
    dsr_prob: float; n_trials: int
    skew: float; kurtosis: float; sample_length: int
```

### 7.6 `survival` — SurvivalChart
```python
class SurvivalChart(BaseModel):
    regimes: list[Regime]                    # 5, enum order
    metrics: list[SurvivalMetric]            # 3, enum order
    values: list[list[float | None]]         # [regime][metric]; null if n_windows == 0
    n_windows: list[int]                     # per regime
    window_days: int                         # 252
    survival_rate: float                     # headline, repeated for the tab header
```

### 7.7 `realism` — RealismReport (also `/generators/{id}/realism`)
```python
class Band(BaseModel):
    p5: float; p50: float; p95: float
class RealismTestOut(BaseModel):
    id: RealismTestId; group: RealismGroup
    name: str; statistic: str
    real: float; synthetic: Band; passed: bool
class ReturnDistribution(BaseModel):
    x: list[float]                           # ≤ 200
    real_density: list[float | None]         # null where 0 (log y-axis)
    syn_p5: list[float | None]; syn_p50: list[float | None]; syn_p95: list[float | None]
    real_kurtosis: float; syn_kurtosis_p50: float
class VolClustering(BaseModel):
    lags: list[int]                          # 1..50
    real: list[float]; syn_p5: list[float]; syn_p50: list[float]; syn_p95: list[float]
class RealismReport(BaseModel):
    generator: GeneratorType; n_paths: int
    passed: int; total: int                  # e.g. 7 / 8
    tests: list[RealismTestOut]              # 8, RealismTestId order
    return_distribution: ReturnDistribution
    vol_clustering: VolClustering
```

### 7.8 `price` — PriceChart (gzip; may exceed 50 KB raw)
```python
class Signal(BaseModel):
    date: date; side: Literal["buy", "sell"]; price: float
class PriceChart(BaseModel):
    ohlc: list[OHLCRow]                      # real history of the audit
    signals: list[Signal]                    # selected variant's position changes
    variant: dict[str, float]
```

---

## 8. Errors

Shape (every 4xx/5xx, every route):
```json
{ "error": { "code": "invalid_grid", "message": "slow must be greater than fast for at least two variants", "details": [ { "loc": ["strategy", "grid", "slow"], "msg": "..." } ] } }
```
```python
class FieldError(BaseModel):
    loc: list[str | int]; msg: str
class ErrorBody(BaseModel):
    code: str; message: str; details: list[FieldError] | None = None
class ErrorResponse(BaseModel):
    error: ErrorBody
```

| HTTP | code | Raised when |
|---|---|---|
| 404 | `audit_not_found` | unknown audit id |
| 404 | `generator_not_found` | unknown generator id |
| 409 | `chart_not_ready` | chart requested before `done` |
| 409 | `realism_not_ready` | generator realism not built |
| 413 | `request_too_large` | body > 16 KB |
| 422 | `invalid_request` | any other schema/type error (Pydantic) |
| 422 | `invalid_grid` | §5.6 grid rules |
| 422 | `invalid_date_range` | §5.6 date rules |
| 422 | `too_many_histories` | n_histories > MAX_HISTORIES |
| 422 | `generator_not_trained` | generator unavailable |
| 503 | `market_data_unavailable` | cache miss and yfinance down |
| 503 | `queue_unavailable` | Redis down and `JOB_MODE=rq` |
| 500 | `internal_error` | anything else (message is safe, no stack trace) |

Audit **job** failures do not produce HTTP errors: the audit gets `status = "error"`, `error = {code, message}`, and the SSE `error` event carries the same pair. Job error codes: `market_data_unavailable`, `generator_failed`, `backtest_failed`, `metrics_failed`, `timeout`, `internal_error`.

---

## 9. Change control

1. **Nobody edits a contract-covered name, field, enum value, unit or shape in code first.**
2. Open a PR titled `contract: <change>` that edits only this file (plus §10 if relevant) and bumps the version:
   - **patch** (`1.0.x`): wording, examples, clarifications — producer may merge.
   - **minor** (`1.x.0`): additive (new optional field, new endpoint) — needs 👍 from every consumer of that boundary.
   - **major** (`x.0.0`): rename/remove/retype — needs 👍 from all three people.
3. After merge: producer implements; A runs `pnpm gen:api` (or C does) and commits `frontend/src/api/schema.d.ts`; `contract_version` in `/health` is bumped; a line goes into `docs/HANDOFFS.md`.
4. CI fails if `schema.d.ts` is stale against `/openapi.json`.
5. Agents: if a task seems to need a contract change, **stop and ask your human** — do not "just add a field".

---

## 10. Decisions this contract made where the spec was silent

Review these at kickoff; change through §9.

| ID | Decision | Why |
|---|---|---|
| D-01 | Ownership follows the WORKFLOW diagram (A: data, generators, backend; B: backtest, metrics incl. realism; C: frontend), not the build-plan lane labels | user instruction; spec says the split is a suggestion |
| D-02 | "Selected variant" = best real-history Sharpe; drives fan, Sharpe histogram, survival, DSR, signals | spec uses "the strategy's chosen variant" without defining it |
| D-03 | Templates use close prices only | synthetic histories have no OHLC |
| D-04 | Long/flat only, signal at close t, held t→t+1, costs per unit position change | not specified |
| D-05 | Concrete param names, ranges and default grids for momentum / RSI / breakout | spec only names templates |
| D-06 | Headline `survival_rate` = share of histories where strategy Sharpe > buy-and-hold Sharpe; regime `survival` = share of 252-day windows with Sharpe > 0 | spec uses "survival" for both; the headline example says "beat buy-and-hold" |
| D-07 | `deflated_sharpe` = annualized (SR − SR0); kurtosis reported raw (normal = 3) | spec lists the field without a formula |
| D-08 | ω = rank/(V+1) in CSCV so logits are finite; drop first `T mod 16` rows | avoids ±inf; needed for equal blocks |
| D-09 | 4 SSE stages; aggregate + verdict report under `metrics` | FR-06 lists 4 stages, pipeline has 6 steps |
| D-10 | Added `real_rank` to fan payload | spec wants percentile rank on hover |
| D-11 | Added endpoints `/charts/fan/paths`, `/charts/realism`, `/charts/price` | sample-path toggle, Realism tab and signal markers need data and the 50 KB cap |
| D-12 | Realism `synthetic` is a `{p5,p50,p95}` band, 8 scalar tests | pass rule needs the band; multi-lag facts need a scalar |
| D-13 | Survival field renamed `n_paths` → `n_windows` | it counts windows, not paths |
| D-14 | Limits: 2–64 variants, ≤ 10 values/param, date range ≥ 3 years from ≥ 2008-01-01 | DSR needs N ≥ 2; CSCV and 252-day windows need length |
| D-15 | `reuse_cached` + `config_hash` dedupe; retry = re-POST config | presets must load instantly; spec has no retry endpoint |
| D-16 | Thresholds returned in `AuditDetail` | tiles must show "threshold used" |
