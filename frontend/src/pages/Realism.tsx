import { useState } from "react";
import { useGenerators, useRealism } from "../api/hooks";
import type { RealismReport } from "../api/types";
import { Realism } from "../components/AuditCharts";
export default function RealismPage() {
  const generators = useGenerators(),
    [id, setId] = useState("garch"),
    report = useRealism<RealismReport>(id);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">GENERATOR LAB</div>
          <h1>Different histories. Familiar markets.</h1>
          <p>
            Inspect how synthetic returns match the stylized facts of the real
            Nifty 50.
          </p>
        </div>
      </div>
      <div className="generator-tabs">
        {generators.data?.map((g) => (
          <button
            className={id === g.id ? "active" : ""}
            key={g.id}
            onClick={() => setId(g.id)}
          >
            {g.name}
            {!g.available && <span className="tag">Coming soon</span>}
          </button>
        ))}
      </div>
      {generators.error && <p role="alert">{generators.error.message}</p>}
      <Realism
        data={report.data}
        pending={report.isPending}
        error={report.error}
      />
    </>
  );
}
