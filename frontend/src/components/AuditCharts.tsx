import { useRef, useState, useContext, type ReactNode } from "react";
import { CompareRanges } from "../lib/compareRanges";
import ReactECharts from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { LineChart, BarChart, ScatterChart, CustomChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  DataZoomComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";
import { Download, Info } from "lucide-react";
import { useChart } from "../api/hooks";
import type {
  FanChart,
  FanPaths,
  SharpeChart,
  PBOChart,
  DSRChart,
  SurvivalChart,
  RealismReport,
  PriceChart as PricePayload,
} from "../api/types";
import { chartTheme } from "../lib/echartsTheme";
import { fmtPct, fmtSharpe, fmtDrawdown } from "../lib/format";
import PriceChart from "./PriceChart";
const accent = "#7565dc",
  grey = "#adb3c0";
echarts.use([
  LineChart,
  BarChart,
  ScatterChart,
  CustomChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  DataZoomComponent,
  CanvasRenderer,
]);
function Chart({
  name,
  option,
  height = 280,
  group,
}: {
  name: string;
  option: EChartsOption;
  height?: number;
  group?: string;
}) {
  const ref = useRef<ReactECharts>(null);
  const shared = useContext(CompareRanges)[name];
  return (
    <>
      <button
        className="export-button"
        aria-label="Export chart as PNG"
        title="Export PNG"
        onClick={() => {
          const href = ref.current?.getEchartsInstance().getDataURL({
            type: "png",
            pixelRatio: 2,
            backgroundColor: "#fff",
          });
          if (href) {
            const a = document.createElement("a");
            a.href = href;
            a.download = "multiverse-chart.png";
            a.click();
          }
        }}
      >
        <Download size={14} />
      </button>
      <ReactECharts
        ref={ref}
        echarts={echarts}
        option={{
          ...chartTheme(),
          ...option,
          xAxis: { ...chartTheme().xAxis, ...option.xAxis, ...shared?.xAxis },
          yAxis: { ...chartTheme().yAxis, ...option.yAxis, ...shared?.yAxis },
          tooltip: { ...chartTheme().tooltip, ...option.tooltip },
        }}
        style={{ height }}
        onChartReady={(chart) => {
          if (group) {
            chart.group = group;
            echarts.connect(group);
          }
        }}
      />
    </>
  );
}
function Card({
  title,
  subtitle,
  explanation,
  children,
}: {
  title: string;
  subtitle: string;
  explanation: string;
  children: ReactNode;
}) {
  return (
    <section className="panel chart-card">
      <div className="chart-heading">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        <a
          href={`/methods.html#${explanation}`}
          title={`Explain this chart: ${explanation}`}
          aria-label={`Explain ${explanation}`}
        >
          <Info size={15} />
        </a>
      </div>
      {children}
    </section>
  );
}
function State({
  pending,
  error,
  empty = false,
  children,
}: {
  pending: boolean;
  error: Error | null;
  empty?: boolean;
  children: ReactNode;
}) {
  if (pending)
    return <div className="chart-placeholder skeleton">Loading evidence…</div>;
  if (error)
    return (
      <div role="alert" className="chart-placeholder">
        {error.message}
      </div>
    );
  if (empty)
    return (
      <div className="chart-placeholder">
        No observations available for this chart.
      </div>
    );
  return children;
}
export function Fan({ id, yRange }: { id: string; yRange?: [number, number] }) {
  const q = useChart<FanChart>(id, "fan"),
    [show, setShow] = useState(false),
    paths = useChart<FanPaths>(id, "fan/paths", show);
  const d = q.data;
  const line = (
    name: string,
    data: number[],
    color: string,
    dashed = false,
  ) => ({
    name,
    type: "line" as const,
    data: data.map((v, i) => [Date.parse(d!.dates[i]), v]),
    symbol: "none",
    lineStyle: {
      color,
      width: name === "Your strategy" ? 2 : 1,
      type: dashed ? ("dashed" as const) : ("solid" as const),
    },
  });
  return (
    <Card
      title={
        d
          ? `Your result sits above ${fmtPct(d.real_rank.at(-1) || 0)} of histories`
          : "Where your backtest sits in the multiverse"
      }
      subtitle={`${d?.n_histories.toLocaleString() || "—"} histories · Growth of ₹1 after costs`}
      explanation="survival"
    >
      <State
        pending={q.isPending}
        error={q.error}
        empty={d?.dates.length === 0}
      >
        {d && (
          <>
            <div className="chart-toggles">
              <label>
                <input
                  type="checkbox"
                  checked={show}
                  onChange={(e) => setShow(e.target.checked)}
                />{" "}
                Show 10 alternate histories
              </label>
              <span>
                <i className="legend-accent" /> Your strategy{" "}
                <i className="legend-neutral" /> Multiverse
              </span>
            </div>
            <Chart
              name="fan"
              height={360}
              group={`audit-${id}`}
              option={{
                xAxis: {
                  type: "time",
                  axisLabel: {
                    formatter: (s: number) =>
                      new Date(s).toISOString().slice(0, 7),
                  },
                },
                yAxis: {
                  type: "value",
                  min: yRange?.[0],
                  max: yRange?.[1],
                  axisLabel: { formatter: (v: number) => `₹${v.toFixed(1)}` },
                },
                dataZoom: [
                  {
                    type: "slider",
                    height: 16,
                    bottom: 5,
                    borderColor: "#e9eaf0",
                    fillerColor: "#ddd7f2",
                  },
                ],
                tooltip: {
                  trigger: "axis",
                  formatter: (params: unknown) => {
                    const p = (params as { dataIndex: number }[])[0],
                      i = p.dataIndex;
                    return `${d.dates[i]}<br/>Your strategy: ₹${d.real[i].toFixed(2)}<br/>Percentile: ${fmtPct(d.real_rank[i])}`;
                  },
                },
                series: [
                  {
                    ...line("5th percentile", d.p5, "transparent"),
                    stack: "outer",
                    areaStyle: { color: "transparent" },
                    silent: true,
                  },
                  {
                    ...line(
                      "5–95% range",
                      d.p95.map((v, i) => v - d.p5[i]),
                      "transparent",
                    ),
                    stack: "outer",
                    areaStyle: { color: "#e8eaf0" },
                    silent: true,
                  },
                  {
                    ...line("25th percentile", d.p25, "transparent"),
                    stack: "inner",
                    areaStyle: { color: "transparent" },
                    silent: true,
                  },
                  {
                    ...line(
                      "25–75% range",
                      d.p75.map((v, i) => v - d.p25[i]),
                      "transparent",
                    ),
                    stack: "inner",
                    areaStyle: { color: "#c7ccd7" },
                    silent: true,
                  },
                  line("Median", d.p50, "#8e96a6", true),
                  ...(show && paths.data
                    ? paths.data.paths.map((p, i) =>
                        line(`Path ${paths.data.path_ids[i]}`, p, "#c2c6cf"),
                      )
                    : []),
                  line("Your strategy", d.real, accent),
                ],
              }}
            />
            {paths.error && show && (
              <p className="field-error">{paths.error.message}</p>
            )}
          </>
        )}
      </State>
    </Card>
  );
}
export function Sharpe({
  id,
  xRange,
}: {
  id: string;
  xRange?: [number, number];
}) {
  const q = useChart<SharpeChart>(id, "sharpe"),
    d = q.data;
  return (
    <Card
      title={
        d
          ? `${fmtPct(d.pct_beaten)} of histories beat your real Sharpe`
          : "How exceptional was your Sharpe?"
      }
      subtitle="Annualized Sharpe · Risk-free rate 0 · 40 bins"
      explanation="dsr"
    >
      <State pending={q.isPending} error={q.error}>
        {d && (
          <Chart
            name="sharpe"
            option={{
              xAxis: {
                type: "value",
                min: xRange?.[0],
                max: xRange?.[1],
                name: "Annualized Sharpe",
              },
              yAxis: { type: "value", name: "Histories" },
              series: [
                {
                  type: "bar",
                  data: d.counts.map((v, i) => [
                    (d.bins[i] + d.bins[i + 1]) / 2,
                    v,
                  ]),
                  itemStyle: { color: grey },
                  barWidth: "95%",
                  markLine: {
                    symbol: "none",
                    data: [{ xAxis: d.real_sharpe, name: "Your strategy" }],
                    lineStyle: { color: accent, width: 2 },
                    label: { formatter: "Your strategy" },
                  },
                },
              ],
            }}
          />
        )}
      </State>
    </Card>
  );
}
export function Pbo({ id }: { id: string }) {
  const q = useChart<PBOChart>(id, "pbo"),
    d = q.data;
  return (
    <>
      <Card
        title={
          d
            ? `${fmtPct(d.pbo)} of selections fell below the OOS median`
            : "Does the best backtest travel?"
        }
        subtitle="PBO = share of logits at or below zero · All CSCV splits"
        explanation="pbo"
      >
        <State pending={q.isPending} error={q.error}>
          {d && (
            <Chart
              name="pbo"
              option={{
                xAxis: {
                  type: "value",
                  min: -6,
                  max: 6,
                  name: "OOS rank logit",
                },
                yAxis: { type: "value", name: "Splits" },
                series: [
                  {
                    type: "bar",
                    data: d.counts.map((v, i) => ({
                      value: [(d.logit_bins[i] + d.logit_bins[i + 1]) / 2, v],
                      itemStyle: {
                        color: d.logit_bins[i + 1] <= 0 ? "#d6a1a8" : grey,
                      },
                    })),
                    markLine: {
                      symbol: "none",
                      data: [{ xAxis: 0 }],
                      lineStyle: { color: "#747b89" },
                    },
                  },
                ],
              }}
            />
          )}
        </State>
      </Card>
      <Card
        title="Does in-sample strength survive out of sample?"
        subtitle={
          d
            ? `Slope ${d.slope.toFixed(2)} · R² ${d.r2.toFixed(2)} · ${d.n_splits.toLocaleString()} splits`
            : "IS vs OOS annualized Sharpe"
        }
        explanation="pbo"
      >
        <State pending={q.isPending} error={q.error}>
          {d && (
            <Chart
              name="scatter"
              option={{
                xAxis: { type: "value", name: "In-sample Sharpe" },
                yAxis: { type: "value", name: "Out-of-sample Sharpe" },
                series: [
                  {
                    type: "scatter",
                    symbolSize: 4,
                    data: d.points.map((p) => [p.is, p.oos]),
                    itemStyle: { color: grey, opacity: 0.45 },
                  },
                  {
                    type: "line",
                    showSymbol: false,
                    data: (() => {
                      const xs = d.points.map((p) => p.is),
                        meanX = xs.reduce((a, b) => a + b, 0) / xs.length,
                        meanY =
                          d.points.reduce((a, b) => a + b.oos, 0) / xs.length;
                      return [Math.min(...xs), Math.max(...xs)].map((x) => [
                        x,
                        meanY + d.slope * (x - meanX),
                      ]);
                    })(),
                    lineStyle: { color: accent, width: 2 },
                  },
                ],
              }}
            />
          )}
        </State>
      </Card>
    </>
  );
}
export function Dsr({ id }: { id: string }) {
  const q = useChart<DSRChart>(id, "dsr"),
    d = q.data;
  return (
    <Card
      title={
        d
          ? `${fmtPct(d.dsr_prob)} probability after selection adjustment`
          : "Adjusting for the parameter search"
      }
      subtitle="Annualized Sharpe · Deflation accounts for multiple trials and non-normal returns"
      explanation="dsr"
    >
      <State pending={q.isPending} error={q.error}>
        {d && (
          <>
            <Chart
              name="dsr"
              option={{
                xAxis: {
                  type: "category",
                  data: [
                    "Raw Sharpe",
                    "Expected noise maximum",
                    "Deflated Sharpe",
                  ],
                },
                yAxis: { type: "value" },
                series: [
                  {
                    type: "bar",
                    data: [
                      { value: d.raw_sharpe, itemStyle: { color: accent } },
                      { value: d.sr0, itemStyle: { color: grey } },
                      {
                        value: d.deflated_sharpe,
                        itemStyle: { color: "#ccc3ea" },
                      },
                    ],
                    barMaxWidth: 65,
                    label: {
                      show: true,
                      position: "top",
                      formatter: (p: { value: unknown }) =>
                        Number(p.value).toFixed(2),
                    },
                  },
                ],
              }}
            />
            <p className="chart-footnote">
              {d.n_trials} trials · Skew {d.skew.toFixed(2)} · Raw kurtosis{" "}
              {d.kurtosis.toFixed(2)} · {d.sample_length.toLocaleString()} daily
              observations
            </p>
          </>
        )}
      </State>
    </Card>
  );
}
export function Survival({ id }: { id: string }) {
  const q = useChart<SurvivalChart>(id, "survival"),
    d = q.data;
  return (
    <Card
      title={
        d
          ? `${fmtPct(d.survival_rate)} of histories beat buy-and-hold`
          : "Survival across market conditions"
      }
      subtitle="Non-overlapping 252-day windows · Regime survival = share with positive Sharpe"
      explanation="survival"
    >
      <State pending={q.isPending} error={q.error}>
        {d && (
          <div className="table-scroll">
            <table className="survival-table">
              <thead>
                <tr>
                  <th>Market regime</th>
                  <th>Survival</th>
                  <th>Median Sharpe</th>
                  <th>Median drawdown</th>
                  <th>Windows</th>
                </tr>
              </thead>
              <tbody>
                {d.regimes.map((r, i) => (
                  <tr key={r}>
                    <th>{r.replaceAll("_", " ")}</th>
                    {d.values[i].map((v, j) => (
                      <td
                        key={j}
                        style={{
                          background:
                            v === null
                              ? "#f8f9fb"
                              : `rgba(117,101,220,${0.04 + 0.18 * (j === 0 ? v : j === 1 ? Math.max(0, Math.min(1, (v + 1) / 3)) : Math.max(0, 1 + v))})`,
                        }}
                      >
                        {v === null
                          ? "—"
                          : j === 0
                            ? fmtPct(v)
                            : j === 1
                              ? fmtSharpe(v)
                              : fmtDrawdown(v)}
                      </td>
                    ))}
                    <td>{d.n_windows[i].toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </State>
    </Card>
  );
}
export function Realism({
  data,
  pending,
  error,
}: {
  data?: RealismReport;
  pending: boolean;
  error: Error | null;
}) {
  const d = data;
  return (
    <>
      <Card
        title={
          d
            ? `${d.passed} of ${d.total} realism checks passed`
            : "Do these histories behave like real markets?"
        }
        subtitle={`${d?.n_paths || "—"} synthetic paths · Real statistic versus 5th–95th percentile band`}
        explanation="realism"
      >
        <State pending={pending} error={error}>
          {d && (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Stylized fact</th>
                    <th>Real</th>
                    <th>Synthetic band</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {d.tests.map((t) => (
                    <tr key={t.id}>
                      <td>{t.name}</td>
                      <td className="mono">{t.real.toFixed(3)}</td>
                      <td className="mono">
                        {t.synthetic.p5.toFixed(3)} –{" "}
                        {t.synthetic.p95.toFixed(3)}
                      </td>
                      <td>
                        <span
                          className={`verdict-chip ${t.passed ? "skill" : "luck"}`}
                        >
                          {t.passed ? "Pass" : "Fail"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </State>
      </Card>
      <div className="charts-grid">
        <Card
          title="Are extreme returns represented?"
          subtitle={
            d
              ? `Log density · Real kurtosis ${d.return_distribution.real_kurtosis.toFixed(2)} · Synthetic median ${d.return_distribution.syn_kurtosis_p50.toFixed(2)}`
              : "Return probability density"
          }
          explanation="realism"
        >
          <State pending={pending} error={error}>
            {d && (
              <Chart
                name="density"
                option={{
                  xAxis: {
                    type: "value",
                    axisLabel: { formatter: (v: number) => fmtPct(v) },
                  },
                  yAxis: { type: "log", min: undefined },
                  series: [
                    {
                      name: "Synthetic 5–95% band",
                      type: "custom",
                      silent: true,
                      data: [0],
                      renderItem: (_params, api) => {
                        const dist = d.return_distribution;
                        const valid = dist.x
                          .map((x, i) => ({
                            x,
                            lo: dist.syn_p5[i],
                            hi: dist.syn_p95[i],
                          }))
                          .filter(
                            (v): v is { x: number; lo: number; hi: number } =>
                              v.lo !== null &&
                              v.hi !== null &&
                              v.lo > 0 &&
                              v.hi > 0,
                          );
                        return {
                          type: "polygon",
                          shape: {
                            points: [
                              ...valid.map((v) => api.coord([v.x, v.lo])),
                              ...valid
                                .reverse()
                                .map((v) => api.coord([v.x, v.hi])),
                            ],
                          },
                          style: { fill: "#e1e4ec", opacity: 0.7 },
                        };
                      },
                    },
                    {
                      name: "Real",
                      type: "line",
                      showSymbol: false,
                      data: d.return_distribution.x.map((x, i) => [
                        x,
                        d.return_distribution.real_density[i],
                      ]),
                      lineStyle: { color: accent, width: 2 },
                    },
                    {
                      name: "Synthetic median",
                      type: "line",
                      showSymbol: false,
                      data: d.return_distribution.x.map((x, i) => [
                        x,
                        d.return_distribution.syn_p50[i],
                      ]),
                      lineStyle: { color: grey, type: "dashed" },
                    },
                    {
                      name: "Synthetic p5",
                      type: "line",
                      showSymbol: false,
                      data: d.return_distribution.x.map((x, i) => [
                        x,
                        d.return_distribution.syn_p5[i],
                      ]),
                      lineStyle: { color: "#d2d6df", width: 1 },
                    },
                    {
                      name: "Synthetic p95",
                      type: "line",
                      showSymbol: false,
                      data: d.return_distribution.x.map((x, i) => [
                        x,
                        d.return_distribution.syn_p95[i],
                      ]),
                      lineStyle: { color: "#d2d6df", width: 1 },
                    },
                  ],
                }}
              />
            )}
          </State>
        </Card>
        <Card
          title="Does volatility remain clustered?"
          subtitle="Autocorrelation of squared returns · Lags 1–50"
          explanation="realism"
        >
          <State pending={pending} error={error}>
            {d && (
              <Chart
                name="vol"
                option={{
                  xAxis: {
                    type: "category",
                    data: d.vol_clustering.lags,
                    name: "Lag (days)",
                  },
                  yAxis: { type: "value" },
                  series: [
                    {
                      name: "Real",
                      type: "line",
                      data: d.vol_clustering.real,
                      showSymbol: false,
                      lineStyle: { color: accent, width: 2 },
                    },
                    {
                      name: "Synthetic median",
                      type: "line",
                      data: d.vol_clustering.syn_p50,
                      showSymbol: false,
                      lineStyle: { color: grey, type: "dashed" },
                    },
                    {
                      type: "line",
                      data: d.vol_clustering.syn_p5,
                      showSymbol: false,
                      stack: "band",
                      lineStyle: { opacity: 0 },
                      areaStyle: { opacity: 0 },
                    },
                    {
                      type: "line",
                      data: d.vol_clustering.syn_p95.map(
                        (v, i) => v - d.vol_clustering.syn_p5[i],
                      ),
                      showSymbol: false,
                      stack: "band",
                      lineStyle: { opacity: 0 },
                      areaStyle: { color: "#e1e4ec" },
                    },
                  ],
                }}
              />
            )}
          </State>
        </Card>
      </div>
    </>
  );
}
export function AuditRealism({ id }: { id: string }) {
  const q = useChart<RealismReport>(id, "realism");
  return <Realism data={q.data} pending={q.isPending} error={q.error} />;
}
export function AuditPrice({ id }: { id: string }) {
  const q = useChart<PricePayload>(id, "price");
  return (
    <Card
      title="The trades behind your real backtest"
      subtitle="Nifty 50 daily closes · Selected variant · Buy and sell signals"
      explanation="survival"
    >
      <State pending={q.isPending} error={q.error}>
        {q.data && <PriceChart rows={q.data.ohlc} signals={q.data.signals} />}
      </State>
    </Card>
  );
}
