import {
  AuditPrice,
  AuditRealism,
  Dsr,
  Fan,
  Pbo,
  Sharpe,
  Survival,
} from "./AuditCharts";
export default function ReportTabs({ id, tab }: { id: string; tab: string }) {
  if (tab === "Multiverse")
    return (
      <>
        <Fan id={id} />
        <Sharpe id={id} />
      </>
    );
  if (tab === "Overfitting")
    return (
      <>
        <div className="charts-grid">
          <Pbo id={id} />
        </div>
        <Dsr id={id} />
      </>
    );
  if (tab === "Survival") return <Survival id={id} />;
  if (tab === "Realism") return <AuditRealism id={id} />;
  return <AuditPrice id={id} />;
}
