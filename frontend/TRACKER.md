# Frontend build tracker

Contract: 1.0.0. Scope: §1, §5–§8. Local implementation completed after Gate 1 release. Gate 3 PASS: both cached presets render every chart through the real API.

- [x] Write contract validation and formatting tests first.
- [x] Scaffold Vite, React, TypeScript, routing, theme and API query layer.
- [x] Build guided strategy form and benchmark price chart.
- [x] Add explicit mock mode with MSW and SSE progress.
- [x] Verify lint, tests, typecheck and production build.
- [x] Generate API types from backend OpenAPI; delete temporary draft types.
- [x] Receive Gate 1 release from integrator before Phase 2.
- [x] Implement live SSE progress, terminal cleanup, three-failure polling fallback, cancel and retry.
- [x] Render API verdict/headline verbatim, metrics with exact thresholds, configuration and history.
- [x] Render fan bands/sample paths, Sharpe/PBO histograms, IS/OOS scatter, DSR, survival, realism and trade charts.
- [x] Add generator lab, lazy report tabs, PNG exports and shared paired chart axis ranges.
- [x] Render canonical method notes as HTML with working heading anchors.
- [x] Verify responsive builder at 390px with loaded benchmark chart and no horizontal overflow.
- [x] Add Docker build, nginx API proxy and SPA fallback.

## Verification

- `pnpm lint`: PASS.
- `pnpm test`: PASS, 7 tests across validation, display units and comparison ranges.
- `pnpm typecheck`: PASS.
- `pnpm build`: PASS; lazy chart bundle produces a size advisory.
- `pnpm test:e2e`: PASS against the real local API: Home → Builder validation → cached preset → Run → Report, every chart tab for both presets, History, every Compare tab, method anchors and mobile layout. No browser page errors.
- Screenshots: `test-results/home-desktop.png`, `builder-desktop.png`, `report-desktop.png`, `builder-mobile.png`.

## Limitations

- Local use only; deployment was excluded by the user.
- Current real presets both score Luck; the frontend preserves these results without forcing a Skill label.
- MSW preview mode labels illustrative data explicitly and ends its demonstration progress stream with a mock-only message; full reports use the real backend.
- Human hallway testing and optional dark mode/PDF export were not performed.
