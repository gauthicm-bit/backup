# Multiverse v2

Audit close-only Nifty 50 strategies across reproducible synthetic market histories. A FastAPI worker fits GJR-GARCH with Student-t innovations to the selected real history, tests every grid variant after costs, and reports PBO, Deflated Sharpe, survival and market realism. React renders the evidence without recomputing metrics.

The binding interface is [API_CONTRACT.md](docs/API_CONTRACT.md), version **1.0.0**. All four strategy templates, the REST/SSE boundary and all eight chart payloads are implemented. TimeGAN and diffusion remain unavailable until trained and validated.

## Run locally

Requirements: Python 3.12 or 3.13, uv, Node 24 and pnpm 11. Commands below start from the repository root. PowerShell is shown.

```powershell
cd backend
uv sync --frozen
Copy-Item .env.example .env
uv run python -m app.cli warm-presets
uv run python -m app.cli build-realism
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open [the app](http://localhost:5173), [API docs](http://localhost:8000/docs), or [health](http://localhost:8000/api/v1/health). The example backend environment selects `JOB_MODE=inprocess`, which needs no Redis. Health correctly reports degraded when Redis is absent. Running `warm-presets` again reuses completed reports.

After installing dependencies, Windows users can also run `./scripts/start-local.ps1` from the repository root to start both servers in the background. Logs are written to `.local-logs/`.

The launcher finds Node.js from your PATH, standard installation folders, or the installed Codex runtime. It checks Node before starting servers and waits for both URLs to respond. For another installation, set `$env:MULTIVERSE_NODE_EXE = 'C:\path\to\node.exe'` before running the script.

The committed price cache contains genuine Yahoo Finance Nifty data from 2008-01-01 through 2026-11-13. The loader downloads on a coverage miss; an unavailable provider produces an explicit error. Audit output is local under `backend/data/audits/` and is excluded from Git.

## Docker and RQ

```powershell
docker compose up --build
docker compose exec api uv run python -m app.cli warm-presets
docker compose exec api uv run python -m app.cli build-realism
```

Compose runs web, API, RQ worker, Redis and Postgres. The web server proxies `/api/` to the API and rewrites SPA routes. API and worker share audit and generator-report volumes. For an external deployment set `FRONTEND_ORIGIN`, the frontend API URL, `DATABASE_URL`, `REDIS_URL` and persistent `DATA_DIR`. Cloud deployment is outside the current local-running scope. Docker is not installed on this machine, so that configuration has not been executed here.

## Verify

```powershell
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=engine.backtest --cov=engine.metrics --cov=engine.realism --cov-fail-under=85
uv run python -m app.cli export-openapi
cd ../frontend
pnpm gen:api:file
pnpm lint
pnpm test
pnpm typecheck
pnpm build
pnpm test:e2e
```

API integration tests use isolated SQLite databases, genuine cached prices and real GARCH samples. No live Yahoo request is needed for those tests. Browser tests require the local API and frontend; install Chromium with `pnpm exec playwright install chromium` when needed. CI checks lint, tests, coverage, build and stale generated types.

## Scientific status

- Gate 1 passes: real market data → GARCH → worker → API result and SSE.
- The synthetic noise and planted-edge tests produce Luck and Skill respectively.
- The overfit preset produces Luck. The initial slow trend preset also produces Luck, so **Gate 2's real-preset requirement is unmet**. Neither thresholds nor preset outcomes are forced.
- GARCH's fixed 2010–2025, 500-path, seed-42 realism report passes **5/8**, below the expected 6/8 smoke target.
- See [method notes](docs/methods.md) and [handoffs](docs/HANDOFFS.md) for formulas, caveats and gate evidence.

The demo preset names describe hypotheses, not promised verdicts. These statistical diagnostics are research evidence and do not guarantee future performance.
