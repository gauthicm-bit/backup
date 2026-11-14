import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Check, LoaderCircle, ArrowRight } from "lucide-react";
import { API_BASE, request } from "../api/client";
import { useAudit, useCreateAudit } from "../api/hooks";
import type { Progress, Stage } from "../api/types";
import { Button } from "../components/ui/button";
const stages: Stage[] = ["fetch", "simulate", "backtest", "metrics"];
const labels = [
  "Fetch market history",
  "Generate alternate histories",
  "Backtest every variant",
  "Measure skill and luck",
];
export default function Run() {
  const { id = "" } = useParams(),
    navigate = useNavigate(),
    client = useQueryClient();
  const [poll, setPoll] = useState(false),
    [progress, setProgress] = useState<Progress | null>(null),
    [error, setError] = useState(""),
    [elapsed, setElapsed] = useState(0);
  const audit = useAudit(id, poll),
    retry = useCreateAudit();
  useEffect(() => {
    setPoll(false);
    setProgress(null);
    setError("");
    setElapsed(0);
    let failures = 0;
    const source = new EventSource(`${API_BASE}/audits/${id}/events`);
    source.addEventListener("progress", (event) =>
      setProgress(JSON.parse((event as MessageEvent).data)),
    );
    const terminal = () => {
      source.close();
      void client.invalidateQueries({ queryKey: ["audit", id] });
    };
    source.addEventListener("done", terminal);
    source.addEventListener("cancelled", terminal);
    source.addEventListener("error", (event) => {
      if ((event as MessageEvent).data) {
        setError(JSON.parse((event as MessageEvent).data).message);
        terminal();
      } else if (++failures >= 3) {
        source.close();
        setPoll(true);
      }
    });
    return () => source.close();
  }, [id, client]);
  useEffect(() => {
    if (audit.data?.status === "done") {
      const timer = setTimeout(
        () => navigate(`/audit/${id}`, { replace: true }),
        2500,
      );
      return () => clearTimeout(timer);
    }
  }, [audit.data?.status, id, navigate]);
  useEffect(() => {
    const timer = setInterval(() => {
      if (audit.data?.started_at)
        setElapsed(
          Math.max(
            0,
            Math.floor(
              ((audit.data.finished_at
                ? Date.parse(audit.data.finished_at)
                : Date.now()) -
                Date.parse(audit.data.started_at)) /
                1000,
            ),
          ),
        );
    }, 1000);
    return () => clearInterval(timer);
  }, [audit.data?.started_at, audit.data?.finished_at]);
  const current = progress || audit.data?.progress,
    index =
      audit.data?.status === "done"
        ? 4
        : stages.indexOf(current?.stage || "fetch");
  const failed = error || audit.data?.error?.message || audit.error?.message;
  const cancelled = audit.data?.status === "cancelled";
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR AUDIT IS RUNNING</div>
          <h1>Exploring the other possibilities.</h1>
          <p>
            Every alternate history gets the same strategy and the same rules.
          </p>
        </div>
        <span className="mono">
          {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
        </span>
      </div>
      <div className="panel run-panel">
        {stages.map((s, i) => (
          <div className={`run-stage ${i === index ? "current" : ""}`} key={s}>
            <span className="run-icon">
              {i < index ? (
                <Check size={17} />
              ) : i === index && !failed && !cancelled ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                i + 1
              )}
            </span>
            <div>
              <h3>{labels[i]}</h3>
              <p>
                {i < index
                  ? "Completed"
                  : i === index
                    ? current?.message || "Waiting for worker…"
                    : "Waiting"}
              </p>
              <div className="progress-track">
                <div
                  style={{
                    width: `${i < index ? 100 : i === index ? current?.pct || 0 : 0}%`,
                  }}
                />
              </div>
            </div>
            <span className="mono">
              {i < index ? "100" : i === index ? current?.pct || 0 : 0}%
            </span>
          </div>
        ))}
        {failed && (
          <div role="alert" className="error-state">
            <h3>We couldn’t finish this audit</h3>
            <p>{failed}</p>
            {audit.data && (
              <Button
                disabled={retry.isPending}
                onClick={async () => {
                  const r = await retry.mutateAsync(audit.data.config);
                  setError("");
                  navigate(`/audit/${r.audit_id}/run`);
                }}
              >
                Retry audit
              </Button>
            )}
            {retry.error && <p>{retry.error.message}</p>}
          </div>
        )}
        {cancelled && (
          <p role="status">
            Audit cancelled.{" "}
            <Link to="/audit/new">
              Build another strategy <ArrowRight size={14} />
            </Link>
          </p>
        )}
        <div className="run-footer">
          <span className="mono">{id}</span>
          {audit.data?.status === "done" ? (
            <span>Audit complete. Opening report…</span>
          ) : (
            !cancelled && (
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    await request(`/audits/${id}`, { method: "DELETE" });
                    await client.invalidateQueries({ queryKey: ["audit", id] });
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Cancel audit
              </Button>
            )
          )}
        </div>
      </div>
    </>
  );
}
