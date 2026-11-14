# AGENTS.md — Multiverse v2 (read this first)

Multiverse tells a quant whether a backtest shows **skill or luck** by re-running the strategy on 1,000+ synthetic Nifty 50 histories and scoring it with PBO, the Deflated Sharpe Ratio and a Survival Map. React + TypeScript frontend, FastAPI + RQ worker backend, all quant code in Python.

> If your tool reads `CLAUDE.md` instead of `AGENTS.md`, copy or symlink this file to `CLAUDE.md`.

## 1. Read order (every session, every agent)

1. **This file.**
2. **`docs/API_CONTRACT.md`** — the single source of truth for every name, field, unit, endpoint and file shape between roles.
3. **Your role file:**
   - Person A → `docs/lifecycle/PERSON_A.md` (Data · Generators · Backend)
   - Person B → `docs/lifecycle/PERSON_B.md` (Backtest · Metrics)
   - Person C → `docs/lifecycle/PERSON_C.md` (Frontend)
4. **`docs/HANDOFFS.md`** — the latest entries tell you what is ready and what is stubbed.

If you don't know which role you are working for, **ask your human before writing code.**

## 2. Who owns what

| Role | Owns (write access) | Never edits |
|---|---|---|
| **A** | `backend/app/**`, `backend/engine/data/**`, `backend/engine/generators/**`, `backend/engine/aggregate/**`, `backend/engine/common.py`, `backend/models/**`, `docker-compose.yml`, deploy + CI config | `engine/backtest`, `engine/metrics`, `engine/realism`, `frontend/` |
| **B** | `backend/engine/backtest/**`, `backend/engine/metrics/**`, `backend/engine/realism/**`, their tests | `app/`, `engine/data`, `engine/generators`, `engine/aggregate`, `frontend/` |
| **C** | `frontend/**` | anything under `backend/` |
| shared | `docs/API_CONTRACT.md` (only via contract PRs), `docs/HANDOFFS.md` (append-only), `README.md` | — |

`notebooks/` is research only and is never imported by the app.

## 3. Pipeline at a glance

```
1 Data (A) ─real returns─▶ 2 Generators (A) ─N histories─▶ 3 Backtest (B) ─returns + Sharpes─▶ 4 Metrics (B) ─scores + verdict─▶ 5 Backend (A) ─REST + SSE─▶ 6 Frontend (C)
      └──────────── real Nifty returns: grid search (→ 3) + realism benchmark (→ 4) ────────────┘
```

## 4. Shared timeline and gates (36-hour build window)

GARCH end to end first; the deep model and polish layer on after. **Nobody moves past Gate 1 until a GARCH audit runs through the real API.**

| Phase | Hours | A | B | C |
|---|---|---|---|---|
| 1 Skeleton | 0–6 | FastAPI, Redis, RQ worker, price cache, GARCH, stub wiring | templates, grid, contract-shaped stubs, then real runner | Vite app, routes, theme, generated types, builder form (on mocks) |
| **Gate 1** | h6 | **A GARCH audit runs end to end through the API** — owner A | | |
| 2 Core engine | 6–16 | SSE, list/get/delete, worker integration, TimeGAN training | vectorbt runner, PBO, DSR, survival, verdict + tests | Run page (SSE), verdict banner + tiles, history table |
| **Gate 2** | h16 | **A pure-noise strategy scores Luck; the robust preset scores Skill** — owner B | | |
| 3 Charts | 16–28 | chart payload endpoints, cached presets, error + retry, realism payloads, TimeGAN ship/no-ship | realism scorecard, threshold tuning, presets, performance | fan chart, histograms, survival heatmap, realism tab |
| **Gate 3** | h28 | **Both presets render every chart with real data** — owner C | | |
| 4 Polish + demo | 28–36 | deploy API/worker/Redis, pytest in CI, in-process fallback, generator lab data | method notes for judges, metric verification | compare page, loading/empty/error states, hallway test |
| **Demo ready** | h36 | **Deployed, both presets cached, demo script rehearsed** — owner A, all rehearse | | |

## 5. Lifecycle of every unit of work (all roles)

1. **Pick** a task from your role file's current phase. Mark it in your tracker / GitHub Issue.
2. **Read the contract sections** the task touches. Quote the section number (e.g. `§5.6`) in the issue/PR.
3. **Branch** `a/<topic>`, `b/<topic>` or `c/<topic>` from `main`.
4. **Write the test first** where the contract gives a shape or rule (schemas, enums, formulas, validation).
5. **Implement** inside your owned folders only.
6. **Verify locally:** `uv run ruff check . && uv run pytest` (backend) / `pnpm lint && pnpm test && pnpm typecheck` (frontend).
7. **PR** to `main` with: what changed, contract sections touched, how you tested. CI must be green. The consumer of the boundary reviews when one is touched.
8. **Hand off:** if another role can now use what you built, append to `docs/HANDOFFS.md`:
   ```
   ## 2026-11-14 14:20 · A → C · contract 1.0.0
   Ready: GET /audits/{id}/events streams real progress (§6). Stubbed: metrics values are fake until B's PR #12.
   ```
9. **Gate check:** at each gate, the gate owner runs the gate's check from their role file and records PASS/FAIL in `docs/HANDOFFS.md`.

## 6. Contract rules (summary of API_CONTRACT §9)

- Never rename, retype or add a contract-covered field in code first. Open a `contract:` PR that edits `docs/API_CONTRACT.md` and bumps its version.
- Additive changes need a 👍 from the consumer; breaking changes need all three people.
- After a backend schema change: `pnpm gen:api`, commit `frontend/src/api/schema.d.ts`. CI fails on stale types.
- **Agents:** if a task seems to require a contract change, stop and ask your human.

## 7. Global conventions

- Ratios are fractions 0–1; Sharpe is annualized (√252, rf = 0); equity starts at 1.0; dates `YYYY-MM-DD`; timestamps UTC `Z`; JSON `snake_case`; no NaN in JSON (use `null`).
- Same config + seed → identical results. Never use unseeded randomness in engine code.
- No user code execution — strategies come only from templates.
- Python: uv, Ruff, pytest, type hints everywhere. TS: pnpm, ESLint + Prettier, Vitest, Playwright smoke test.
- Colour rules (C): one accent = "your strategy"; greys = multiverse; green/amber/red only for verdicts and pass/fail.

## 8. Local run

```bash
docker compose up                         # api, worker, redis, db, web
# or without Docker:
cd backend && uv run uvicorn app.main:app --reload
cd backend && uv run rq worker audits
redis-server
cd frontend && pnpm dev
cd frontend && pnpm gen:api               # after any backend schema change
```

## 9. Backup and push authorization

- Backup repository: `https://github.com/gauthicm-bit/backup.git`.
- Push to GitHub only when the user explicitly requests a push or upload. The initial backup upload is authorized; this is not standing permission for later pushes.
- After the initial backup, keep subsequent changes local until the user explicitly authorizes another push.
