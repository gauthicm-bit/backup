import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAudit, useAudits, useChart } from "../api/hooks";
import type {
  FanChart,
  SharpeChart,
  PBOChart,
  DSRChart,
  RealismReport,
  PriceChart,
} from "../api/types";
import { CompareRanges, comparisonRanges } from "../lib/compareRanges";
import { Metrics, VerdictBanner } from "./Report";
import {
  Fan,
  Sharpe,
  Survival,
  Dsr,
  Pbo,
  AuditRealism,
  AuditPrice,
} from "../components/AuditCharts";
function useComparison(id: string, tab: string) {
  return {
    fan: useChart<FanChart>(id, "fan", tab === "Multiverse").data,
    sharpe: useChart<SharpeChart>(id, "sharpe", tab === "Multiverse").data,
    pbo: useChart<PBOChart>(id, "pbo", tab === "Overfitting").data,
    dsr: useChart<DSRChart>(id, "dsr", tab === "Overfitting").data,
    realism: useChart<RealismReport>(id, "realism", tab === "Realism").data,
    price: useChart<PriceChart>(id, "price", tab === "Trades").data,
  };
}
export default function Compare() {
  const [params, setParams] = useSearchParams(),
    [tab, setTab] = useState("Multiverse"),
    a = params.get("a") || "",
    b = params.get("b") || "",
    audits = useAudits(),
    left = useAudit(a),
    right = useAudit(b);
  const ranges = comparisonRanges([
    useComparison(a, tab),
    useComparison(b, tab),
  ]);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">COMPARE AUDITS</div>
          <h1>The evidence, side by side.</h1>
          <p>
            Choose two completed audits. Paired charts share the same scale.
          </p>
        </div>
      </div>
      <div className="compare-selectors">
        {[
          ["a", a],
          ["b", b],
        ].map(([key, value]) => (
          <label key={key}>
            Audit {key.toUpperCase()}
            <select
              value={value}
              onChange={(e) => {
                const next = new URLSearchParams(params);
                next.set(key, e.target.value);
                setParams(next);
              }}
            >
              <option value="">Choose a completed audit</option>
              {audits.data?.items
                .filter((i) => i.status === "done")
                .map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.template.replaceAll("_", " ")} · {i.start} · {i.verdict}{" "}
                    · {i.id.slice(-6)}
                  </option>
                ))}
            </select>
          </label>
        ))}
      </div>
      {audits.error && <p role="alert">{audits.error.message}</p>}
      <div className="report-tabs" role="tablist" aria-label="Compare evidence">
        {["Multiverse", "Overfitting", "Survival", "Realism", "Trades"].map(
          (t) => (
            <button
              key={t}
              role="tab"
              aria-selected={t === tab}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ),
        )}
      </div>
      <CompareRanges.Provider value={ranges}>
        <div className="compare-grid">
          {[left, right].map((q, i) => (
            <div key={i}>
              {!q.data ? (
                <div className="panel empty-state">
                  {q.error
                    ? q.error.message
                    : "Choose an audit above to compare its evidence."}
                </div>
              ) : q.data.status !== "done" ? (
                <div className="panel empty-state">
                  This audit is {q.data.status}.
                </div>
              ) : (
                <>
                  <VerdictBanner audit={q.data} />
                  <Metrics audit={q.data} />
                  {tab === "Multiverse" ? (
                    <>
                      <Fan id={q.data.id} />
                      <Sharpe id={q.data.id} />
                    </>
                  ) : tab === "Overfitting" ? (
                    <>
                      <Pbo id={q.data.id} />
                      <Dsr id={q.data.id} />
                    </>
                  ) : tab === "Survival" ? (
                    <Survival id={q.data.id} />
                  ) : tab === "Realism" ? (
                    <AuditRealism id={q.data.id} />
                  ) : (
                    <AuditPrice id={q.data.id} />
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      </CompareRanges.Provider>
    </>
  );
}
