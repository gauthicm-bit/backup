# Handoffs log (append-only)

Every role appends here when something another role can use is ready, when a stub is replaced, and at every gate. Newest at the bottom. Never edit old entries.

Format:

```
## YYYY-MM-DD HH:MM · <from> → <to> · contract <version>
Ready: <what works, with contract §>
Stubbed: <what is still fake, and until when>
Gate: <Gate N PASS/FAIL — only for gate entries>
```

---

## 2026-11-14 · all · contract 1.0.0
Ready: AGENTS.md, docs/API_CONTRACT.md, docs/lifecycle/PERSON_{A,B,C}.md committed. Review contract §10 decisions at kickoff.

## 2026-11-14 · B → A · contract 1.0.0
Ready: Four template grids (§2.4, §5.4, §5.6), real batched MA backtest (§2.4), eight-statistic realism (§2.5), metric interfaces, exact verdict headlines. Scoped Ruff and 15 tests pass.
Stubbed: PBO, DSR, regime survival until Gate 1 passes. Other strategy runners pending Phase 2. Preset target verdicts unverified.


## 2026-11-14 · A → all · contract 1.0.0
Ready: Gate 1 real GARCH audit through FastAPI and the shared in-process worker; genuine Nifty cache, parquet persistence, fetch→simulate→backtest→metrics events, terminal SSE and cache reuse (§§2–6). API tests: 11 passed, data/generators: 17 passed, B phase1: 15 passed.
Stubbed: PBO, DSR and regime survival are phase1 stubs; replacing in Phase 2. RQ deployment not yet exercised.
Gate: Gate 1 PASS — real API integration test, real market data, real fitted GJR-GARCH and worker (inprocess fallback).

## 2026-11-14 · B → A/C · contract 1.0.0
Ready: Real four-template batched backtests, PBO 12,870 CSCV splits, DSR, regime survival, eight realism tests, exact verdicts (§2.4–§2.5). 36 scoped tests pass, 97% engine coverage, Ruff clean. Published DSR treasury example reproduces 0.9004 and paper PBO rank example passes. docs/methods.md documents methods and tie policy. Default 1,000 × 3,928 × 16 MA backtest measured 2.931 s locally.
Stubbed: No B metric or runner stubs remain. Offline deep generators remain A scope.
Gate: Gate 2 FAIL — synthetic noise→Luck and planted edge→Skill pass, but real presets both score Luck. Overfit PBO 0.555478 / DSR 0.962859 / survival 0.183; slow-trend baseline 0.530070 / 0.954371 / 0.244. Limited four-template search across ten date windows found no honest Skill candidate. Contract thresholds unchanged; no preset special cases.


## 2026-11-14 · A → C · contract 1.0.0
Ready: All REST endpoints, full OpenAPI schemas, RQ/shared in-process pipeline, local cached presets, generator realism, all eight real chart payloads (§§3–8). Reproducibility verified with forced recomputation: metrics and chart response bytes identical. Backend final suite: 76 passed; engine coverage 98.69%; Ruff check/format pass.
Stubbed: No active GARCH pipeline or metric stubs. TimeGAN/diffusion intentionally unavailable. Docker/RQ/Postgres configuration provided but not runtime-tested on this Windows host (Docker absent). Cloud deployment explicitly out of scope per user.

## 2026-11-14 · C → all · contract 1.0.0
Ready: Generated API types; all routes; SSE run/cancel/retry; real reports with threshold tiles; lazy charts; history, shared-scale comparison, generator lab, rendered methods and responsive layouts (§§5–8). Frontend: 7 Vitest tests, ESLint, typecheck and production build pass. Playwright on real API: both cached presets, every report and comparison tab, builder validation, methods links, history, mobile chart and no overflow; no page errors. Screenshot evidence in frontend/test-results (local artifacts).
Gate: Gate 3 PASS — both cached presets render all real chart data. Gate 2 remains FAIL on the honest real-preset Skill requirement; no scores or thresholds altered.

## 2026-11-14 · all · local delivery · contract 1.0.0
Ready: Final app responds at http://127.0.0.1:5173 and API at http://127.0.0.1:8000. scripts/start-local.ps1 restarts both. User explicitly selected local use, no deployment. Final real-API browser smoke on port 5173 records no console or page errors; mobile benchmark fits the full selected history. Generated schema SHA256 9F633C199F43AD7A344652C64232D09C7D7C3F34D89ED4A769D744487EE9F278.
Remaining: Gate 2 preset Skill criterion unmet; GARCH realism 5/8; optional deep generators unavailable. Local inprocess mode is verified; Redis/RQ/Postgres/Docker runtime and human hallway testing are unverified.
