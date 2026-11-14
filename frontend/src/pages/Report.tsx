import { lazy, Suspense, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Info } from "lucide-react";
import { useAudit, useCreateAudit } from "../api/hooks";
import type { AuditDetail } from "../api/types";
import { fmtPct, fmtSharpe } from "../lib/format";
const Charts = lazy(() => import("../components/ReportTabs"));
export function Metrics({ audit }: { audit: AuditDetail }) {
  const m = audit.metrics,
    t = audit.thresholds;
  if (!m) return null;
  return (
    <div className="metric-grid">
      {[
        {
          label: "Probability of overfitting",
          value: m.pbo,
          method: "pbo",
          note: "How often the winning variant disappoints out of sample.",
          threshold: `Skill threshold: < ${fmtPct(t.pbo_skill_max)}`,
        },
        {
          label: "Deflated Sharpe probability",
          value: m.dsr_prob,
          method: "dsr",
          note: "Evidence of an edge after adjusting for selection.",
          threshold: `Skill threshold: ≥ ${fmtPct(t.dsr_skill_min)}`,
        },
        {
          label: "Survival rate",
          value: m.survival_rate,
          method: "survival",
          note: "Share of alternate histories that beat buy-and-hold.",
          threshold: `Skill threshold: ≥ ${fmtPct(t.survival_skill_min)}`,
        },
      ].map((v) => (
        <section className="panel metric" key={v.method}>
          <div>
            <h3>{v.label}</h3>
            <a
              href={`/methods.html#${v.method}`}
              title={v.note}
              aria-label={`Explain ${v.label}`}
            >
              <Info size={14} />
            </a>
          </div>
          <strong>{fmtPct(v.value)}</strong>
          <p>{v.note}</p>
          <span>{v.threshold}</span>
        </section>
      ))}
    </div>
  );
}
export function VerdictBanner({ audit }: { audit: AuditDetail }) {
  return (
    <section className={`panel verdict-banner ${audit.verdict}`}>
      <span className={`verdict-chip ${audit.verdict}`}>
        {audit.verdict || "Pending"}
      </span>
      <h2>{audit.headline || "Waiting for the completed audit."}</h2>
      <p>
        {audit.config.generator.n_histories.toLocaleString()} alternate
        histories · {audit.derived.n_trials} variants · Seed{" "}
        {audit.config.generator.seed}
      </p>
    </section>
  );
}
export default function Report() {
  const { id = "" } = useParams(),
    audit = useAudit(id),
    retry = useCreateAudit(),
    navigate = useNavigate(),
    [tab, setTab] = useState("Multiverse");
  if (audit.isPending)
    return <div className="panel loading">Loading audit evidence…</div>;
  if (audit.error)
    return (
      <div className="panel error-state" role="alert">
        <h1>
          {audit.error.message.includes("not found")
            ? "Audit not found"
            : "Could not load this audit"}
        </h1>
        <p>{audit.error.message}</p>
        <Link className="button outline" to="/history">
          Back to history
        </Link>
      </div>
    );
  const a = audit.data!;
  if (a.status !== "done")
    return (
      <div className="panel pending-page">
        <h1>Audit {a.status}</h1>
        <p>
          {a.error?.message ||
            "Your report will be available when the audit finishes."}
        </p>
        {a.status === "queued" || a.status === "running" ? (
          <Link className="button primary" to={`/audit/${id}/run`}>
            View progress <ArrowRight size={16} />
          </Link>
        ) : (
          <button
            className="button primary"
            onClick={async () => {
              const r = await retry.mutateAsync(a.config);
              navigate(`/audit/${r.audit_id}/run`);
            }}
          >
            Retry this audit
          </button>
        )}
        {retry.error && <p>{retry.error.message}</p>}
      </div>
    );
  return (
    <>
      <Link className="back-link" to="/history">
        <ArrowLeft size={15} /> Back to history
      </Link>
      <div className="page-heading">
        <div>
          <div className="eyebrow">THE EVIDENCE IS IN</div>
          <h1>Beyond one backtest.</h1>
          <p>
            {a.config.strategy.template.replaceAll("_", " ")} · Nifty 50 ·{" "}
            {a.config.start} — {a.config.end}
          </p>
        </div>
        <Link className="button outline" to={`/compare?a=${id}`}>
          Compare this audit
        </Link>
      </div>
      <VerdictBanner audit={a} />
      <Metrics audit={a} />
      <details className="panel config-summary">
        <summary>
          Audit configuration <span className="mono">{id}</span>
        </summary>
        <div>
          <p>
            <strong>Template</strong>{" "}
            {a.config.strategy.template.replaceAll("_", " ")}
          </p>
          <p>
            <strong>Selected parameters</strong>{" "}
            {Object.entries(a.derived.selected_variant?.params || {})
              .map(([k, v]) => `${k} = ${v}`)
              .join(" · ")}
          </p>
          <p>
            <strong>Real Sharpe</strong>{" "}
            {a.derived.selected_variant
              ? fmtSharpe(a.derived.selected_variant.real_sharpe)
              : "—"}
          </p>
          <p>
            <strong>Generator</strong> {a.config.generator.type} ·{" "}
            {a.config.generator.n_histories.toLocaleString()} histories
          </p>
          <p>
            <strong>Seed / costs</strong> {a.config.generator.seed} /{" "}
            {a.config.costs_bps} bps
          </p>
          <p>
            <strong>Trials</strong> {a.derived.n_trials}
          </p>
        </div>
      </details>
      <div className="report-tabs" role="tablist" aria-label="Audit evidence">
        {["Multiverse", "Overfitting", "Survival", "Realism", "Trades"].map(
          (name, i) => (
            <button
              id={`tab-${i}`}
              key={name}
              role="tab"
              aria-selected={tab === name}
              aria-controls="evidence-panel"
              tabIndex={tab === name ? 0 : -1}
              onClick={() => setTab(name)}
              onKeyDown={(e) => {
                if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                  const next = (i + (e.key === "ArrowRight" ? 1 : 4)) % 5;
                  setTab(
                    [
                      "Multiverse",
                      "Overfitting",
                      "Survival",
                      "Realism",
                      "Trades",
                    ][next],
                  );
                  document.getElementById(`tab-${next}`)?.focus();
                }
              }}
            >
              {name}
            </button>
          ),
        )}
      </div>
      <div id="evidence-panel" role="tabpanel">
        <Suspense
          fallback={
            <div className="panel chart-placeholder">Loading charts…</div>
          }
        >
          <Charts id={id} tab={tab} />
        </Suspense>
      </div>
    </>
  );
}
