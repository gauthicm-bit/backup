import { ArrowRight, FlaskConical, GitBranch, ShieldCheck } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useCreateAudit, usePresets } from "../api/hooks";
export default function Home() {
  const presets = usePresets(),
    create = useCreateAudit(),
    navigate = useNavigate();
  return (
    <>
      <div className="hero">
        <div className="eyebrow">A SECOND OPINION FOR YOUR BACKTEST</div>
        <h1>
          Was it skill.
          <br />
          Or a lucky universe?
        </h1>
        <p>
          Test your strategy across alternate Nifty 50 histories.
          <br />
          Find out whether your edge survives beyond the backtest.
        </p>
        <Link className="button primary" to="/audit/new">
          Audit your strategy <ArrowRight size={17} />
        </Link>
        <span className="hero-caption">
          Four templates · Reproducible results · No code required
        </span>
      </div>
      <div className="feature-row">
        {[
          [
            GitBranch,
            "1,000+ alternate histories",
            "The same market character. A different sequence of events.",
          ],
          [
            FlaskConical,
            "Three independent checks",
            "Overfitting, deflated Sharpe and survival across regimes.",
          ],
          [
            ShieldCheck,
            "One honest verdict",
            "Skill, luck or inconclusive — with the evidence behind it.",
          ],
        ].map(([Icon, title, text]) => (
          <div className="panel feature" key={String(title)}>
            {typeof Icon !== "string" && <Icon size={24} />}
            <h3>{String(title)}</h3>
            <p>{String(text)}</p>
          </div>
        ))}
      </div>
      <div className="section-title">
        <div>
          <div className="eyebrow">START WITH A QUESTION</div>
          <h2>Two strategies. Put both to the test.</h2>
        </div>
        <span>Preconfigured examples</span>
      </div>
      <div className="preset-grid">
        {presets.data?.map((p, i) => (
          <button
            className="panel preset"
            disabled={create.isPending}
            key={p.id}
            onClick={async () => {
              const r = await create.mutateAsync(p.config);
              navigate(`/audit/${r.audit_id}/run`);
            }}
          >
            <span className="preset-number">0{i + 1}</span>
            <div>
              <h3>{p.name}</h3>
              <p>{p.description}</p>
            </div>
            <ArrowRight size={21} />
          </button>
        ))}
      </div>
      {presets.error && <p role="alert">{presets.error.message}</p>}
      {create.error && <p role="alert">{create.error.message}</p>}
    </>
  );
}
