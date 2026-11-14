# Person A — Lifecycle: Data · Generators · Backend

Read `AGENTS.md` and `docs/API_CONTRACT.md` first. Section numbers (§) below refer to the contract.

## 1. Mission

You own both ends of the pipeline's plumbing: getting real Nifty 50 data in (stage 1), turning it into synthetic histories (stage 2), and the whole backend service (stage 5) — FastAPI, Redis, the RQ worker that runs every audit, storage, and the chart JSON the frontend reads. You are also the **integrator**: B's engine code only becomes a product when your worker calls it, and C's UI only works when your API matches the contract exactly.

## 2. Scope

| You own | Folder |
|---|---|
| Price loader + Parquet cache | `backend/engine/data/` |
| Generators: GARCH (baseline), TimeGAN (challenger, optional), diffusion (stretch) | `backend/engine/generators/`, `backend/models/` |
| Shared engine exceptions/types | `backend/engine/common.py` |
| Chart payload builders | `backend/engine/aggregate/` |
| FastAPI app, routers, schemas, DB, worker, settings | `backend/app/` |
| Docker Compose, deploy, CI workflows | repo root, `.github/` |

**Not yours:** `engine/backtest`, `engine/metrics`, `engine/realism` (B), `frontend/` (C). If B's code blocks you, ask B or use the stubs from Phase 1 — don't patch their modules.

## 3. Interfaces

| You **provide** | To | Contract |
|---|---|---|
| `load_prices`, `log_returns` | B (tests, notebooks), worker | §2.2 |
| `Generator` interface + `get_generator` | B (tests), worker | §2.3 |
| `engine/common.py` exceptions + `ProgressFn` | B | §2.1 |
| Every REST endpoint, the SSE stream, every chart payload | C | §5, §6, §7 |
| Error shape and codes | C | §8 |
| `/openapi.json` that generates complete TS types | C | §5 general rules |

| You **consume** | From | Contract |
|---|---|---|
| `TEMPLATES`, `expand_grid`, `run_backtest` → `BacktestResult` | B | §2.4 |
| `compute_pbo`, `compute_dsr`, `compute_survival`, `compute_survival_rate`, `run_realism`, `decide_verdict` | B | §2.5 |
| `PRESETS` | B | §2.7 |

## 4. Lifecycle by phase

### Phase 0 — Kickoff (first 30 min, all three people)
- [ ] Create the monorepo layout from the spec (`backend/`, `frontend/`, `notebooks/`, `docs/`), commit `AGENTS.md` + `docs/`.
- [ ] `backend/pyproject.toml` with uv; Ruff; pytest; pin `arch`, `vectorbt`, `pandas`, `numpy`, `pyarrow`, `fastapi`, `sqlmodel`, `rq`, `redis`, `sse-starlette`, `pydantic-settings`, `yfinance`.
- [ ] Create `engine/common.py` (§2.1) and empty packages `engine/{data,generators,backtest,metrics,realism,aggregate}` with `__init__.py` so B can start immediately.
- [ ] GitHub Actions: Ruff + pytest on backend; ESLint + Vitest + typecheck on frontend; stale-types check (§9.4).
- [ ] Review contract §10 decisions with B and C; merge any changes as `contract:` PRs before coding.

### Phase 1 — Skeleton (hours 0–6)
**Data**
- [ ] `load_prices` with Parquet cache at `data/cache/prices/^NSEI.parquet`; yfinance only on cache miss; raises `MarketDataUnavailable` (§2.2).
- [ ] Pre-fetch 2008-01-01 → today and **commit the demo cache** (risk fallback for yfinance outages).
- [ ] `log_returns`; unit tests: shape `(T,)`, no NaN, matches `np.log(c[1:]/c[:-1])`.

**Generators**
- [ ] `Generator` ABC (§2.3), `GarchGenerator` = GJR-GARCH(1,1) with Student-t/skewed-t via `arch`.
- [ ] `sample()` deterministic in seed; test: same seed → identical array; different seed → different.
- [ ] Return-windows dataset script for TimeGAN (sliding windows of log returns) → hand to Colab/Kaggle.

**Backend**
- [ ] `app/core/settings.py` with every var in §4.1; storage path helpers for §3.1.
- [ ] SQLModel tables (§3.2); SQLite in dev.
- [ ] Pydantic schemas for **every** model in §5 and §7, with enums from §1.1. This is what C's types come from — do it first.
- [ ] Error handlers: custom shape (§8) for `HTTPException`, `RequestValidationError` (→ `invalid_request` or the specific code), `EngineError`, and catch-all 500.
- [ ] Routes: `/health`, `/market/prices`, `/strategies/templates` (from B's `TEMPLATES`, or a stub until B lands it), `/generators`, `/presets` (stub), `POST /audits`, `GET /audits/{id}`.
- [ ] RQ queue `audits`, worker `run_audit(audit_id)` (§4.2), progress publisher (§4.3) writing both the channel and `audit:{id}:last`.
- [ ] **Stub adapter** `app/worker/engine_stubs.py`: if B's functions aren't merged yet, return objects with the exact §2.4/§2.5 dataclass shapes and plausible fake numbers. Remove as B's PRs land.
- [ ] Publish `openapi.json`; tell C to run `pnpm gen:api`; append to `docs/HANDOFFS.md`.

**Gate 1 check (you own it, hour 6):**
```bash
curl -X POST localhost:8000/api/v1/audits -H 'content-type: application/json' \
  -d '{"symbol":"^NSEI","start":"2010-01-01","end":"2025-12-31","strategy":{"template":"ma_crossover","grid":{"fast":[5,10,20,30],"slow":[50,100,150,200]}},"generator":{"type":"garch","n_histories":100,"seed":42},"costs_bps":5}'
# → 202 {"audit_id": ..., "status": "queued", "cached": false}
curl -N localhost:8000/api/v1/audits/<id>/events     # progress fetch→simulate→backtest→metrics, then done
curl localhost:8000/api/v1/audits/<id>               # status "done", verdict + metrics present
```
PASS = real GARCH paths, real worker, real API; metrics may still be B's stubs. Record PASS/FAIL in `docs/HANDOFFS.md`. **Nobody moves on until this passes.**

### Phase 2 — Core engine (hours 6–16)
- [ ] `GET /audits/{id}/events` SSE (§6): terminal-state short-circuit, replay `:last`, relay channel, 15 s ping, correct headers.
- [ ] `GET /audits` (pagination, status filter), `DELETE /audits/{id}` (cancel flag → `Cancelled`; delete folder + row) (§5.8, §5.9).
- [ ] Swap stubs for B's real `run_backtest` and metrics as each PR merges; wire B's `progress` callbacks into SSE `pct`.
- [ ] Write `paths.parquet` (float32), `returns_real.parquet`, `sharpe_matrix.parquet`, `config.json` (§3.1).
- [ ] Persist `versions` and `config_hash`; implement `reuse_cached` (§4.4).
- [ ] Job failure path: catch → `status=error`, `error_code`, message → SSE `error` (§8 job codes).
- [ ] **TimeGAN** (parallel, GPU, optional): train on Colab/Kaggle; save weights to `backend/models/` or a release asset; `TimeGANGenerator.load()`; chaining windows to full length.
- [ ] Support B for Gate 2: make sure their noise-strategy and preset tests can run through the worker.

### Phase 3 — Charts (hours 16–28)
- [ ] `engine/aggregate/`: one builder per payload §7.1–§7.8. Rules: ≤ 500 dates by even stride (keep first + last), 40-bin histograms with **edges**, logits clipped to [−6, 6], ≤ 1000 PBO points (seed 0), `null` for NaN, `is` alias for PBO points.
- [ ] Unit test each builder: lengths match, `sum(counts) == n`, payload JSON ≤ 50 KB for 5,000 histories × 64 variants × 18 years (except `price`).
- [ ] Chart routes `/audits/{id}/charts/*` with 404/409 rules (§5.1).
- [ ] `warm-presets` CLI: run both of B's `PRESETS`, store `cached_audit_id`; `/presets` returns it.
- [ ] Generator realism: CLI `build-realism` → `data/generators/{type}/realism.json`; `/generators/{id}/realism`; set `realism_passed`.
- [ ] **TimeGAN decision** at ~hour 24: if it passes B's realism scorecard, mark `available: true`; else ship GARCH only, `available: false` ("coming soon").
- [ ] GZip middleware; check every non-job endpoint ≤ 300 ms.

**Gate 3 support:** both presets' every chart endpoint returns 200 with real data. C owns the gate; you fix any payload issue they find same-hour.

### Phase 4 — Polish + demo (hours 28–36)
- [ ] Deploy API + worker + Redis (Railway / Render / Fly.io); Postgres via `DATABASE_URL`; CORS = deployed frontend origin.
- [ ] `JOB_MODE=inprocess` fallback using FastAPI `BackgroundTasks` (same `run_audit`, same progress publishing).
- [ ] pytest in CI green; stale-types check green.
- [ ] Generator lab page data complete for every generator.
- [ ] Run `warm-presets` on the deployed stack.
- [ ] **Demo-ready check (you own it):** deployed URL works from a fresh browser; both presets load from cache in seconds; full 3-minute script rehearsed by all three.

## 5. Tests you must have
- Data: cache hit doesn't call yfinance (mock it); cache miss writes Parquet; outage → `MarketDataUnavailable`.
- Generators: determinism; shape/NaN; GARCH realism smoke test via B's `run_realism` (expect ≥ 6/8 pass).
- API: one test per endpoint for success + each listed error code; OpenAPI contains every §5/§7 model.
- SSE: late subscriber gets `:last` replay; terminal audits close immediately.
- Worker: end-to-end on a 3-year range, 100 histories, MA grid → `done` in < 30 s.
- Reproducibility: same config + seed twice → identical `metrics` and chart JSON bytes.

## 6. Risks you own (spec fallbacks)
| Risk | Fallback |
|---|---|
| TimeGAN/diffusion not ready or fails realism | GARCH only; deep models `available: false` |
| yfinance down | committed Parquet cache for the demo range |
| Audits too slow on demo machine | default 500 histories; presets served from cache |
| Redis/worker trouble on host | `JOB_MODE=inprocess` |
| Contract drift | generated TS types + CI stale check |

## 7. Definition of done (A)
All §5 endpoints and §6 SSE match the contract byte-for-byte in shape; every §7 payload built from B's real results; presets cached on the deployed stack; Gate 1 and Demo-ready recorded PASS in `docs/HANDOFFS.md`.
