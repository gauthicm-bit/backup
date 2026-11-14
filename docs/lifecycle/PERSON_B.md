# Person B — Lifecycle: Backtest · Metrics

Read `AGENTS.md` and `docs/API_CONTRACT.md` first. Section numbers (§) below refer to the contract.

## 1. Mission

You own the science. Stage 3 runs every strategy variant on the real history and on every synthetic history; stage 4 decides whether the result is skill or luck — realism tests, PBO (CSCV), Deflated Sharpe, Survival Map and the verdict. Your code is pure Python with **no web, Redis, DB or file I/O**: it takes arrays and returns the dataclasses in §2.4–§2.5. If your numbers are wrong, the whole product lies, so correctness tests are your main deliverable.

## 2. Scope

| You own | Folder |
|---|---|
| Strategy templates, grid expansion, demo presets | `backend/engine/backtest/templates.py`, `presets.py` |
| Vectorised multiverse runner (vectorbt) | `backend/engine/backtest/runner.py` |
| PBO, DSR, survival, verdict | `backend/engine/metrics/{pbo,dsr,survival,verdict}.py` |
| Stylized-fact realism tests | `backend/engine/realism/stylized_facts.py` |
| Their tests | `backend/tests/{backtest,metrics,realism}/` |

**Not yours:** `engine/data`, `engine/generators`, `engine/aggregate`, `engine/common.py` (A; you may *add* an exception there, never rename), `app/` (A), `frontend/` (C). You never build chart JSON — A's aggregate does that from your dataclasses.

## 3. Interfaces

| You **provide** | To | Contract |
|---|---|---|
| `TEMPLATES`, `TemplateSpec`, `ParamSpec`, `Constraint`, `expand_grid` | A (serves `/strategies/templates`, validates POST) → C | §2.4, §5.4 |
| `run_backtest` → `BacktestResult` | A's worker | §2.4 |
| `compute_pbo`, `compute_dsr`, `compute_survival`, `compute_survival_rate` | A's worker | §2.5 |
| `run_realism` → `RealismResult` | A's worker + generator lab | §2.5 |
| `Thresholds`, `decide_verdict` → `VerdictResult` (incl. headline text) | A | §2.5 |
| `PRESETS` (overfit, robust) | A (`/presets`, `warm-presets`) | §2.7 |

| You **consume** | From | Contract |
|---|---|---|
| `load_prices`, `log_returns` (for tests/notebooks) | A | §2.2 |
| `Generator.sample()` output `(n_paths, T)` log returns | A | §2.3 |
| `ProgressFn`, `Cancelled`, `InvalidGrid` | A (`engine/common.py`) | §2.1 |

Until A's GARCH lands, generate test paths yourself with a seeded i.i.d. Student-t or block bootstrap of `r_real` — same shape `(n_paths, T)`.

## 4. Lifecycle by phase

### Phase 0 — Kickoff (first 30 min)
- [ ] Read §2.4–§2.7 and §10 (D-02 to D-08, D-12 to D-14 are yours). Object now, via a `contract:` PR, or never.
- [ ] Port the relevant research-notebook code into the module layout; notebooks stay in `notebooks/` and are never imported.

### Phase 1 — Skeleton (hours 0–6)
- [ ] `templates.py`: the four templates exactly as §5.4 table (names, types, ranges, steps, constraints, default grids).
- [ ] `expand_grid`: Cartesian product in `ParamSpec` order, values ascending, constraints applied, all §5.6 grid rules → `InvalidGrid` with a human message naming the param.
- [ ] Tests: default grids give 16 / 12 / 8 / 8 variants; ordering is deterministic; each invalid case raises.
- [ ] **By hour 4 — stubs for A's Gate 1:** functions with the final signatures returning the final dataclasses (correct shapes, plausible numbers). Merge them so A can wire the worker. Append a `B → A` line to `docs/HANDOFFS.md`.
- [ ] Start the real `run_backtest` for `ma_crossover` on the real history only.
- [ ] `realism/stylized_facts.py`: the 8 tests of §2.5 (one scalar each) plus density and ACF-of-r² bands.

### Phase 2 — Core engine (hours 6–16)
**Backtest**
- [ ] Real `run_backtest` for all four templates: long/flat, signal at close *t* held *t → t+1*, costs `bps/10_000 × |Δpos|`, warm-up = flat (§2.4 rules).
- [ ] Vectorise across paths with vectorbt (or NumPy). **Batch paths** (e.g. 100–250 per batch) so memory stays well under 2 GB — never hold `(n_paths, T, V)` returns at once. Keep only `sharpe_paths (n_paths, V)` plus the selected variant's `(n_paths, T)` returns.
- [ ] Selected variant = argmax real Sharpe, ties → lowest index (D-02). Buy-and-hold Sharpe per path.
- [ ] Call `progress(frac)` at least every ~2 s; let `Cancelled` propagate.
- [ ] Perf target: **1,000 histories × 16 variants × ~15 years ≤ 60 s on laptop CPU** (leaves the other 60 s of the 2-minute budget for A's stages).

**Metrics**
- [ ] `compute_pbo`: CSCV, S = 16, 12,870 splits, ω = rank/(V+1), drop first `T mod 16` rows (D-08); return logits, IS/OOS Sharpe per split, OLS slope and r².
- [ ] `compute_dsr`: spec formula; `V[SR_n]` across variants on real; skew γ3; **raw** kurtosis γ4; daily Sharpe inside, annualized outputs; `deflated_sharpe` = annualized (SR − SR0) (D-07).
- [ ] `compute_survival`: non-overlapping 252-day windows; regime rules from §2.5 table; terciles over all windows of all paths; three metric columns; NaN where 0 windows.
- [ ] `compute_survival_rate`: share of paths with selected Sharpe > buy-and-hold Sharpe (D-06).
- [ ] `decide_verdict`: Luck check first, then Skill, else Inconclusive; exact headline templates from §2.5.

**Correctness tests (non-negotiable)**
- [ ] PBO and DSR reproduce worked examples from the source papers (Bailey, Borwein, López de Prado & Zhu for PBO/CSCV; Bailey & López de Prado for DSR) to 3 decimal places — put the numbers and citation in the test docstring.
- [ ] DSR edge cases: N = 2 works; identical variants don't divide by zero.
- [ ] PBO sanity: V identical noise variants → PBO ≈ 0.5; one variant with strong planted edge among noise → PBO near 0.
- [ ] Regime rules on hand-built windows (a −25% window is `crash`, not `trend_down`).
- [ ] Determinism: same inputs → identical outputs.

**Gate 2 check (you own it, hour 16):**
- [ ] A **pure-noise strategy** (random-entry signal or MA grid on i.i.d. zero-drift paths) → verdict **luck**.
- [ ] A strategy with **built-in edge on synthetic data** → verdict **skill** (spec correctness requirement).
- [ ] `PRESETS["overfit"]` → **luck** and `PRESETS["robust"]` → **skill**, run through A's real worker.
Record PASS/FAIL in `docs/HANDOFFS.md`.

> Risk: a genuinely robust strategy on real Nifty may still miss DSR ≥ 0.95 or survival ≥ 60%. The spec says thresholds are "tuned during testing". If the robust preset can't reach Skill honestly, change the preset first, then thresholds — via a `contract:` PR — and tell the team. Never special-case the presets in code.

### Phase 3 — Charts (hours 16–28)
- [ ] `PRESETS` final: `overfit` (many variants, e.g. 64-variant RSI or momentum grid, short window) and `robust` (small slow-MA grid, long window). Both valid `CreateAuditRequest` bodies.
- [ ] Realism scorecard final for GARCH (expect ≥ 6/8 pass); run it on A's TimeGAN samples for the ship/no-ship call (~hour 24).
- [ ] Check every number A puts in chart payloads against your results for both presets (spot-check fan p50, Sharpe `pct_beaten`, PBO counts sum, survival cells).
- [ ] Profile and optimise the runner if the full audit exceeds 2 minutes.

### Phase 4 — Polish + demo (hours 28–36)
- [ ] **Method notes for judges** (`docs/methods.md`): one paragraph + formula + citation each for realism, PBO, DSR, survival, verdict thresholds. C links tile tooltips to these anchors: `#pbo`, `#dsr`, `#survival`, `#realism`, `#verdict`.
- [ ] Coverage of `engine/backtest`, `engine/metrics`, `engine/realism` in CI ≥ 85%.
- [ ] Rehearse the demo; be ready to explain why the overfit preset is luck.

## 5. Definition of done (B)
All §2.4–§2.5 functions implemented with the exact signatures and dataclasses; paper-example tests pass; noise → Luck, edge → Skill; presets give their target verdicts; full default audit ≤ 2 min end to end; `docs/methods.md` written; Gate 2 recorded PASS.
