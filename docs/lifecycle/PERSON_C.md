# Person C — Lifecycle: Frontend

Read `AGENTS.md` and `docs/API_CONTRACT.md` first. Section numbers (§) below refer to the contract.

## 1. Mission

You own everything the user and the judges see: a four-step guided flow — **Build → Generate → Run → Verdict** — where the verdict is answered in one sentence before any chart, and every chart is polished, readable and explains the verdict. You talk **only** to the FastAPI backend through the generated types; you never compute metrics, only format and draw what the API returns.

## 2. Scope

| You own | Folder |
|---|---|
| Vite + React + TypeScript SPA | `frontend/` |
| Pages | `src/pages/` — Home, Builder, Run, Report, Compare, Realism, History |
| Charts | `src/components/charts/` + `src/lib/echartsTheme.ts` |
| API layer | `src/api/schema.d.ts` (generated), `src/api/client.ts`, `src/api/hooks.ts` |
| Builder store | `src/store/` (Zustand) |

**Not yours:** anything under `backend/`. If a payload is missing something, ask A — don't derive it client-side and don't hand-edit `schema.d.ts`.

Stack (fixed by spec): Vite, React + TS, React Router, TanStack Query, Zustand, Tailwind, shadcn/ui, React Hook Form + Zod, ECharts (`echarts-for-react`), TradingView Lightweight Charts, TanStack Table, Lucide, Inter + JetBrains Mono, `openapi-typescript`, pnpm, ESLint + Prettier, Vitest, Playwright.

## 3. Interfaces

| You **consume** | Endpoint | Contract |
|---|---|---|
| Health + contract version banner | `GET /health` | §5.2 |
| Real price chart in builder | `GET /market/prices` | §5.3 |
| Template picker, param ranges, live variant count | `GET /strategies/templates` | §5.4 |
| Generator picker ("coming soon" when `available: false`) | `GET /generators` | §5.5 |
| Demo buttons | `GET /presets` | §5.10 |
| Start audit | `POST /audits` → 202 | §5.6 |
| Run page progress | `GET /audits/{id}/events` (SSE) | §6 |
| Report, compare, retry | `GET /audits/{id}` | §5.7 |
| History table | `GET /audits` | §5.8 |
| Cancel / delete | `DELETE /audits/{id}` | §5.9 |
| Charts | `GET /audits/{id}/charts/{fan,fan/paths,sharpe,pbo,dsr,survival,realism,price}` | §7 |
| Generator lab | `GET /generators/{id}/realism` | §7.7 |

| You **provide** | To |
|---|---|
| UX bug reports on payloads (shape, size, missing field) | A, via issue with the contract § |
| Hallway-test findings on chart clarity | A, B |

## 4. Lifecycle by phase

### Phase 0 — Kickoff (first 30 min)
- [ ] Read §1 (enums, units — **ratios are 0–1, you format %**), §5–§8. Raise any UI need the contract misses now, as a `contract:` PR.
- [ ] Scaffold with pnpm; Tailwind; shadcn/ui; ESLint + Prettier; Vitest; Playwright.

### Phase 1 — Skeleton (hours 0–6) — build on mocks, never wait for the backend
- [ ] Routes (React Router): `/`, `/audit/new`, `/audit/:id/run`, `/audit/:id`, `/compare?a=&b=`, `/realism`, `/history`. Route-level code splitting. Host rewrite to `index.html` for all routes.
- [ ] `pnpm gen:api` script: `openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts` (schema lives at the server root, not under `/api/v1`). Until A's server is up, hand-write **only** a temporary `src/api/schema.draft.ts` from the contract and delete it once real types exist.
- [ ] **MSW mocks** in `src/mocks/` using the contract examples (§5.6, §5.7) and fake but correctly-shaped chart payloads (§7). Toggle with `VITE_USE_MOCKS=1`. Include an SSE mock that walks the four stages.
- [ ] `api/client.ts`: fetch wrapper with base URL, JSON, and the §8 error shape → typed `ApiError { status, code, message, details }`.
- [ ] TanStack Query hooks, one per endpoint; query keys: `["audit", id]`, `["audits", params]`, `["chart", id, name]`, `["templates"]`, `["generators"]`, `["presets"]`, `["prices", symbol, start, end]`, `["realism", generatorId]`.
- [ ] `lib/echartsTheme.ts` per spec "Chart visual style" table (Inter, horizontal 1 px light grid, no y-axis line, ≤ 6 ticks, ₹ / % / "Jan 2020" formatters, one accent, greys, verdict colours, 300 ms first-draw animation only, fixed heights fan 360 / histogram 280 / heatmap 320). Light + dark token sets.
- [ ] **Strategy builder** `/audit/new`:
  - Step 1: template select, per-param multi-value input within `[min, max]` / `step`, date range (≥ 2008-01-01, ≥ 3 years), **live variant count** computed from `params` × `constraints` exactly like §2.4 `expand_grid`, show error if outside 2–64.
  - Step 2: generator (disabled + "coming soon" when `available: false`), histories 100 / 500 / 1,000 / 5,000, seed, costs (bps).
  - Right side: real Nifty 50 close (Lightweight Charts area series) from `/market/prices`.
  - Zod schema mirrors §5.6 rules; on submit `POST /audits` → navigate to `/audit/:id/run`. Map 422 `details[].loc` to form fields.

### Phase 2 — Core engine (hours 6–16) — switch to the real API after Gate 1
- [ ] Run `pnpm gen:api` against A's server; delete the draft types; fix type errors.
- [ ] **Run page** `/audit/:id/run`: stepper fetch → simulate → backtest → metrics, progress bar per stage (stage-local `pct`), elapsed time from `started_at`, cancel button (`DELETE`). SSE rules from §6: close on terminal event, invalidate `["audit", id]`, after 3 failed reconnects poll `GET /audits/{id}` every 2 s. On `done` → navigate to `/audit/:id`. If the audit was cached, still show the stepper animating for ~2.5 s (demo script step 2). On `error` → message + **Retry** (re-POST `config`).
- [ ] **Verdict banner**: pill with the word (Skill / Luck / Inconclusive — text always present, colour never the only signal) + the backend `headline` sentence verbatim.
- [ ] **Three metric tiles**: PBO, DSR (`dsr_prob`), Survival rate. Each: big number (JetBrains Mono, tabular), one-line meaning, threshold used from `thresholds`, info tooltip linking to `docs/methods.md#pbo|#dsr|#survival`.
- [ ] Config summary (collapsible): template, params, `n_trials`, selected variant, generator, histories, seed.
- [ ] **History** `/history`: TanStack Table — date, strategy, generator, histories, verdict, status; sortable; row click → report (or run page if not done).
- [ ] **Home** `/`: one-line pitch, Overfit / Robust buttons (POST preset `config`), "Audit your strategy" → builder.

### Phase 3 — Charts (hours 16–28)
One component per chart; each has **skeleton loading, empty, and error states**, a finding-style title, a grey subtitle (units + sample size), an "Explain this chart" info icon and an export-PNG button. Fetch each chart only when its tab is visible.

| Tab | Component | Payload | Must show |
|---|---|---|---|
| Multiverse | `FanChart` | §7.1 | grey 5–95 band, darker 25–75, dashed median, accent `real` line; tooltip shows `real_rank` as percentile; dataZoom slider; title e.g. "Real result sits above 95% of histories" |
| Multiverse | sample-paths toggle | §7.2 | 10 thin grey lines, fetched on first toggle |
| Multiverse | `SharpeHistogram` | §7.3 | bars from `bins` edges, accent line at `real_sharpe`, shaded share = `pct_beaten` |
| Overfitting | `PboLogitHistogram` | §7.4 | bars left of 0 tinted red, label "PBO = share left of 0" |
| Overfitting | `IsOosScatter` | §7.4 | points, regression line, slope + r² |
| Overfitting | `DsrBars` | §7.5 | raw vs deflated bars + DSR probability tile + inputs (trials, skew, kurtosis, sample length) |
| Survival | `SurvivalHeatmap` | §7.6 | rows = regimes, cols = metrics, good→bad colour per column, **number printed in every cell**, `null` → "—", `n_windows` per row |
| Realism | `RealismScorecard` | §7.7 | table with pass/fail chips (text + colour), real vs band |
| Realism | `ReturnDensity` | §7.7 | real = accent, synthetic = grey band, **log y-axis**, kurtosis in legend |
| Realism | `VolClustering` | §7.7 | ACF of r², lags 1–50, real line vs band |
| Builder / report | `PriceChart` | §5.3 / §7.8 | Lightweight Charts area of close + buy/sell markers |

- [ ] Synced crosshair between charts on the same tab (`echarts.connect`).
- [ ] Format helpers with tests: `fmtPct(0.31) → "31%"`, `fmtSharpe(0.842) → "0.84"`, `fmtDate("2020-01-31") → "Jan 2020"`, ₹ formatting, drawdown `-0.18 → "−18%"`.
- [ ] `/realism` Generator lab: one report per generator from `/generators/{id}/realism`; handle 409 `realism_not_ready`.

**Gate 3 check (you own it, hour 28):** open both presets' reports on the real backend; every tab's every chart renders real data with no console errors. Record PASS/FAIL in `docs/HANDOFFS.md`; file issues to A/B for any wrong payload.

### Phase 4 — Polish + demo (hours 28–36)
- [ ] **Compare** `/compare?a=&b=`: two reports side by side; **identical axis ranges** on every paired chart (compute shared min/max from both payloads).
- [ ] Loading, empty and error states audited on every page; 404 audit page.
- [ ] Responsive: 12-column grid desktop, single column < 768 px. Keyboard navigation through tabs, tiles, tables.
- [ ] Dark mode (P2) and PDF/PNG export (P2) only if time.
- [ ] Performance: first load ≤ 2 s, chart render ≤ 200 ms, bundle split per route.
- [ ] **Hallway test** with 2–3 people outside the team; rewrite any chart title they misread.
- [ ] Deploy to Vercel/Netlify with SPA rewrite and `VITE_API_BASE_URL`; confirm CORS with A.
- [ ] Playwright smoke: Home → Overfit preset → Run → Report shows "Luck" and the fan chart.

## 5. Design rules (spec, non-negotiable)
- One accent colour = "your strategy". The multiverse is always neutral grey. The real backtest is the only strong line.
- Green / amber / red only for verdicts and pass/fail — never decoration.
- Titles state the finding ("31% of histories beat buy-and-hold"), not the chart type.
- Every metric has a one-sentence tooltip linking to the method.
- No chart ships with ECharts defaults — everything goes through `echartsTheme.ts`.

## 6. Definition of done (C)
Every route works against the deployed API; all types generated (no hand-written API types left); every §7 payload drawn per spec with loading/empty/error states; demo script runs cleanly; Gate 3 recorded PASS.
