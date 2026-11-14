import { lazy, Suspense } from "react";
import { NavLink, Link, Route, Routes } from "react-router-dom";
import {
  ArrowUpRight,
  Box,
  GitCompareArrows,
  History,
  PanelTop,
  Orbit,
} from "lucide-react";
import { useHealth } from "./api/hooks";
const Home = lazy(() => import("./pages/Home")),
  Builder = lazy(() => import("./pages/Builder")),
  Run = lazy(() => import("./pages/Run")),
  Report = lazy(() => import("./pages/Report")),
  HistoryPage = lazy(() => import("./pages/History")),
  Compare = lazy(() => import("./pages/Compare")),
  Realism = lazy(() => import("./pages/Realism"));
export default function App() {
  const health = useHealth();
  return (
    <>
      <header>
        <div className="nav-container">
          <Link className="brand" to="/">
            <span className="brand-mark">
              <Orbit size={24} />
            </span>
            multiverse<span className="version">v2</span>
          </Link>
          <nav aria-label="Main navigation">
            <NavLink to="/audit/new">
              <PanelTop size={15} /> Strategy builder
            </NavLink>
            <NavLink to="/history">
              <History size={15} /> History
            </NavLink>
            <NavLink to="/compare">
              <GitCompareArrows size={15} /> Compare
            </NavLink>
            <NavLink to="/realism">
              <Box size={15} /> Generator lab
            </NavLink>
          </nav>
          <a
            className="docs-link"
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
          >
            API docs <ArrowUpRight size={14} />
          </a>
        </div>
      </header>
      {import.meta.env.VITE_USE_MOCKS === "1" && (
        <div className="notice">
          Preview mode · Market data and progress are illustrative. Audit scores
          require the real backend.
        </div>
      )}
      {health.data && health.data.contract_version !== "1.0.0" && (
        <div className="notice" role="alert">
          API contract mismatch: expected 1.0.0, received{" "}
          {health.data.contract_version}.
        </div>
      )}
      <main>
        <Suspense
          fallback={<div className="panel loading">Loading workspace…</div>}
        >
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/audit/new" element={<Builder />} />
            <Route path="/audit/:id/run" element={<Run />} />
            <Route path="/audit/:id" element={<Report />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/realism" element={<Realism />} />
            <Route path="/compare" element={<Compare />} />
            <Route
              path="*"
              element={
                <div className="panel pending-page">
                  <h1>Page not found</h1>
                  <Link to="/">Return to overview</Link>
                </div>
              }
            />
          </Routes>
        </Suspense>
      </main>
      <footer>
        <span>
          <Orbit size={14} /> Multiverse · Beyond the backtest
        </span>
        <span>Research evidence, not investment advice.</span>
        <span>
          NIFTY 50 <i />{" "}
          {health.isPending
            ? "Connecting…"
            : health.error
              ? "API offline"
              : health.data?.db === "down"
                ? "API degraded"
                : health.data?.job_mode === "inprocess"
                  ? "Local mode"
                  : health.data?.status === "ok"
                    ? "API connected"
                    : "API connected · Redis unavailable"}
        </span>
      </footer>
    </>
  );
}
