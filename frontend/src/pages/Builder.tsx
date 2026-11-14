import { useState } from "react";
import { useForm } from "react-hook-form";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  Info,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import {
  useCreateAudit,
  useGenerators,
  usePrices,
  useTemplates,
} from "../api/hooks";
import { ApiError } from "../api/client";
import type { CreateAuditRequest, TemplateId } from "../api/types";
import { useBuilder } from "../store/builder";
import { expandGrid, parseValues, validateAudit } from "../lib/validation";
import PriceChart from "../components/PriceChart";
import { Button } from "../components/ui/button";
type Fields = {
  start: string;
  end: string;
  costs_bps: number;
  seed: number;
  n_histories: 100 | 500 | 1000 | 5000;
  grid: Record<string, string>;
};
export default function Builder() {
  const { config, save } = useBuilder();
  const [templateId, setTemplateId] = useState<TemplateId>(
    config.strategy.template,
  );
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const templates = useTemplates(),
    generators = useGenerators(),
    create = useCreateAudit(),
    navigate = useNavigate();
  const form = useForm<Fields>({
    defaultValues: {
      start: config.start,
      end: config.end,
      costs_bps: config.costs_bps,
      seed: config.generator.seed,
      n_histories: config.generator.n_histories,
      grid: Object.fromEntries(
        Object.entries(config.strategy.grid).map(([k, v]) => [k, v.join(", ")]),
      ),
    },
  });
  const values = form.watch();
  const template = templates.data?.find((t) => t.id === templateId);
  const prices = usePrices(values.start, values.end);
  let count = 0,
    gridError = "";
  try {
    if (template)
      count = expandGrid(
        template,
        Object.fromEntries(
          template.params.map((p) => [
            p.name,
            parseValues(values.grid?.[p.name] || ""),
          ]),
        ),
      ).length;
  } catch (e) {
    gridError = (e as Error).message;
  }
  const buildConfig = (): CreateAuditRequest => ({
    ...config,
    start: values.start,
    end: values.end,
    strategy: {
      template: templateId,
      grid: Object.fromEntries(
        template!.params.map((p) => [p.name, parseValues(values.grid[p.name])]),
      ),
    },
    generator: {
      type: "garch",
      n_histories: Number(values.n_histories) as 100 | 500 | 1000 | 5000,
      seed: Number(values.seed),
    },
    costs_bps: Number(values.costs_bps),
  });
  async function submit() {
    setError("");
    try {
      const c = buildConfig(),
        result = validateAudit(c, template!);
      if (!result.success) {
        setError(result.error.issues[0].message);
        return;
      }
      save(c);
      if (step === 1) {
        setStep(2);
        return;
      }
      const audit = await create.mutateAsync(c);
      navigate(`/audit/${audit.audit_id}/run`);
    } catch (e) {
      if (e instanceof ApiError && e.details)
        for (const detail of e.details) {
          const key = detail.loc.filter((l) => l !== "body").join(".");
          if (key === "start" || key === "end" || key === "costs_bps")
            form.setError(key, { message: detail.msg });
        }
      setError((e as Error).message);
    }
  }
  if (templates.isPending)
    return <div className="panel loading">Loading strategy catalogue…</div>;
  if (templates.error)
    return (
      <div className="panel error-state">
        <h2>Strategy catalogue unavailable</h2>
        <p>{templates.error.message}</p>
        <Button onClick={() => templates.refetch()}>Try again</Button>
      </div>
    );
  return (
    <>
      <Link className="back-link" to="/">
        <ArrowLeft size={15} /> Back to overview
      </Link>
      <div className="page-heading">
        <div>
          <div className="eyebrow">STRATEGY AUDIT</div>
          <h1>Put your edge to the test.</h1>
          <p>One backtest is a story. A thousand histories are evidence.</p>
        </div>
        <span className="private-note">
          <ShieldCheck size={16} /> No code. No hindsight.
        </span>
      </div>
      <div className="steps">
        <button
          className={step === 1 ? "active" : ""}
          onClick={() => setStep(1)}
        >
          <span>{step > 1 ? <Check size={14} /> : 1}</span> Build your strategy
        </button>
        <i />
        <button
          className={step === 2 ? "active" : ""}
          onClick={() => count >= 2 && count <= 64 && setStep(2)}
        >
          <span>2</span> Generate the multiverse
        </button>
        <i />
        <div>
          <span>3</span> Discover your verdict
        </div>
      </div>
      <div className="builder-grid">
        <form
          className="panel form-panel"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div className="section-heading">
            <span className="section-index">0{step}</span>
            <div>
              <h2>
                {step === 1 ? "Define the strategy" : "Choose your multiverse"}
              </h2>
              <p>
                {step === 1
                  ? "Choose a template and the parameters to explore."
                  : "Replay your strategy across alternate market histories."}
              </p>
            </div>
          </div>
          {step === 1 ? (
            <>
              <label htmlFor="strategy">Strategy template</label>
              <div className="select-wrap">
                <select
                  id="strategy"
                  value={templateId}
                  onChange={(e) => {
                    const t = templates.data!.find(
                      (t) => t.id === e.target.value,
                    )!;
                    setTemplateId(t.id);
                    form.setValue(
                      "grid",
                      Object.fromEntries(
                        Object.entries(t.default_grid).map(([k, v]) => [
                          k,
                          v.join(", "),
                        ]),
                      ),
                    );
                    setError("");
                  }}
                >
                  {templates.data?.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={16} />
              </div>
              <p className="field-hint">{template?.description}</p>
              <div className="divider" />
              <div className="subheading">
                <h3>Parameter search</h3>
                <span>Days, unless specified</span>
              </div>
              {template?.params.map((p) => (
                <div className="field" key={p.name}>
                  <label htmlFor={p.name}>
                    {p.label}
                    <span>
                      {p.min}–{p.max}
                      {p.type === "int" ? " days" : ""}
                    </span>
                  </label>
                  <input
                    id={p.name}
                    {...form.register(`grid.${p.name}`)}
                    placeholder={p.default_values.join(", ")}
                  />
                  <p className="field-hint">Separate values with commas.</p>
                </div>
              ))}
              <div
                className={`variant-count ${count < 2 || count > 64 ? "invalid" : ""}`}
              >
                <div>
                  <Sparkles size={17} />
                  <strong>{count} strategy variants</strong>
                </div>
                <span>2–64 allowed</span>
              </div>
              {gridError && <p className="field-error">{gridError}</p>}
              <div className="divider" />
              <h3>Historical benchmark</h3>
              <div className="field-row">
                <div>
                  <label htmlFor="start">Start date</label>
                  <input
                    id="start"
                    type="date"
                    min="2008-01-01"
                    {...form.register("start")}
                  />
                </div>
                <div>
                  <label htmlFor="end">End date</label>
                  <input id="end" type="date" {...form.register("end")} />
                </div>
              </div>
              <p className="field-hint">
                At least 3 years of Nifty 50 history, from 2008 onwards.
              </p>
            </>
          ) : (
            <>
              <label>Market generator</label>
              <div className="generator-options">
                {generators.data?.map((g) => (
                  <label
                    className={`generator-option ${g.available ? "selected" : ""}`}
                    key={g.id}
                  >
                    <input
                      type="radio"
                      name="generator"
                      checked={g.available}
                      disabled={!g.available}
                      readOnly
                    />
                    <div>
                      <strong>{g.name}</strong>
                      <p>{g.description}</p>
                    </div>
                    {!g.available && <span className="tag">Coming soon</span>}
                  </label>
                ))}
              </div>
              {generators.error && (
                <p className="field-error">{generators.error.message}</p>
              )}
              <label htmlFor="n_histories">Alternate histories</label>
              <select id="n_histories" {...form.register("n_histories")}>
                {[100, 500, 1000, 5000].map((n) => (
                  <option key={n} value={n}>
                    {n.toLocaleString("en-IN")} histories
                  </option>
                ))}
              </select>
              <div className="field-row">
                <div>
                  <label htmlFor="seed">Random seed</label>
                  <input
                    id="seed"
                    type="number"
                    min="0"
                    max="2147483647"
                    {...form.register("seed", { valueAsNumber: true })}
                  />
                </div>
                <div>
                  <label htmlFor="costs">Trading costs (bps)</label>
                  <input
                    id="costs"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    {...form.register("costs_bps", { valueAsNumber: true })}
                  />
                </div>
              </div>
              <div className="info-box">
                <Info size={17} />
                <p>
                  The same configuration and seed produce the same result.
                  Trading costs apply every time a position changes.
                </p>
              </div>
            </>
          )}
          {error && (
            <div role="alert" className="field-error">
              {error}
            </div>
          )}
          <div className="form-footer">
            <span>
              {step === 1
                ? "Next: choose your market generator"
                : "A full audit can take up to 2 minutes."}
            </span>
            <Button
              type="submit"
              disabled={
                create.isPending ||
                !template ||
                count < 2 ||
                count > 64 ||
                !!gridError
              }
            >
              {create.isPending
                ? "Starting…"
                : step === 1
                  ? "Continue"
                  : "Run the audit"}
              <ArrowRight size={16} />
            </Button>
          </div>
        </form>
        <aside>
          <div className="panel market-panel">
            <div className="market-heading">
              <div>
                <span className="eyebrow">YOUR BENCHMARK</span>
                <h2>
                  Nifty 50 <span>NSE · INDIA</span>
                </h2>
              </div>
              <span className="tag">Daily close</span>
            </div>
            {prices.data?.ohlc.length ? (
              <>
                <div className="market-value">
                  ₹
                  {prices.data.ohlc.at(-1)!.close.toLocaleString("en-IN", {
                    maximumFractionDigits: 2,
                  })}
                  <span>Final close in selected range</span>
                </div>
                <PriceChart rows={prices.data.ohlc} />
              </>
            ) : (
              <div className="chart-placeholder">
                {prices.isPending
                  ? "Loading market history…"
                  : prices.error?.message || "No prices in this date range."}
                {prices.error && (
                  <button type="button" onClick={() => prices.refetch()}>
                    Retry
                  </button>
                )}
              </div>
            )}
            <div className="market-caption">
              <span>
                {values.start} — {values.end}
              </span>
              <span>
                {import.meta.env.VITE_USE_MOCKS === "1"
                  ? "Illustrative mock data"
                  : prices.data?.source === "cache"
                    ? "Cached market data"
                    : "Market data"}
              </span>
            </div>
          </div>
          <div className="explanation">
            <div className="icon-orbit">
              <Info size={18} />
            </div>
            <div>
              <h3>Why more than one history?</h3>
              <p>
                Your strategy only saw one version of the market. We create
                alternate histories with similar volatility and tail behaviour
                to see whether its edge holds up.
              </p>
              <a href="/realism">
                Explore the methodology <ArrowRight size={13} />
              </a>
            </div>
          </div>
          <div className="audit-summary">
            <span>THE AUDIT INCLUDES</span>
            <p>
              <Check size={15} /> Probability of backtest overfitting
            </p>
            <p>
              <Check size={15} /> Sharpe ratio adjusted for selection
            </p>
            <p>
              <Check size={15} /> Survival across market regimes
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
