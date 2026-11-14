import { createContext } from "react";
import type {
  FanChart,
  SharpeChart,
  PBOChart,
  DSRChart,
  RealismReport,
  PriceChart,
} from "../api/types";
export type AxisRange = { min?: number; max?: number };
export type SharedRanges = Record<
  string,
  { xAxis?: AxisRange; yAxis?: AxisRange }
>;
export const CompareRanges = createContext<SharedRanges>({});
export interface ComparisonData {
  fan?: FanChart;
  sharpe?: SharpeChart;
  pbo?: PBOChart;
  dsr?: DSRChart;
  realism?: RealismReport;
  price?: PriceChart;
}
export function range(
  values: (number | null | undefined)[],
  includeZero = false,
): AxisRange {
  const numbers = values.filter(
    (v): v is number => v !== null && v !== undefined && Number.isFinite(v),
  );
  if (!numbers.length) return {};
  if (includeZero) numbers.push(0);
  const min = Math.min(...numbers),
    max = Math.max(...numbers),
    pad = max === min ? Math.max(1, Math.abs(min) * 0.05) : 0;
  return { min: min - pad, max: max + pad };
}
export function comparisonRanges(items: ComparisonData[]): SharedRanges {
  const fans = items.flatMap((i) => (i.fan ? [i.fan] : [])),
    sharpes = items.flatMap((i) => (i.sharpe ? [i.sharpe] : [])),
    pbos = items.flatMap((i) => (i.pbo ? [i.pbo] : [])),
    dsrs = items.flatMap((i) => (i.dsr ? [i.dsr] : [])),
    realism = items.flatMap((i) => (i.realism ? [i.realism] : [])),
    prices = items.flatMap((i) => (i.price ? [i.price] : []));
  return {
    fan: {
      xAxis: range(fans.flatMap((d) => d.dates.map((s) => Date.parse(s)))),
      yAxis: range(fans.flatMap((d) => [...d.p5, ...d.p95, ...d.real])),
    },
    sharpe: {
      xAxis: range(sharpes.flatMap((d) => [...d.bins, d.real_sharpe])),
      yAxis: range(
        sharpes.flatMap((d) => d.counts),
        true,
      ),
    },
    pbo: {
      xAxis: { min: -6, max: 6 },
      yAxis: range(
        pbos.flatMap((d) => d.counts),
        true,
      ),
    },
    scatter: {
      xAxis: range(pbos.flatMap((d) => d.points.map((p) => p.is))),
      yAxis: range(pbos.flatMap((d) => d.points.map((p) => p.oos))),
    },
    dsr: {
      yAxis: range(
        dsrs.flatMap((d) => [d.raw_sharpe, d.deflated_sharpe, d.sr0]),
        true,
      ),
    },
    density: {
      xAxis: range(realism.flatMap((d) => d.return_distribution.x)),
      yAxis: range(
        realism
          .flatMap((d) => [
            ...d.return_distribution.real_density,
            ...d.return_distribution.syn_p5,
            ...d.return_distribution.syn_p95,
          ])
          .filter((v) => v !== null && v > 0),
      ),
    },
    vol: {
      xAxis: { min: 0, max: 49 },
      yAxis: range(
        realism.flatMap((d) => [
          ...d.vol_clustering.real,
          ...d.vol_clustering.syn_p5,
          ...d.vol_clustering.syn_p95,
        ]),
        true,
      ),
    },
    price: {
      xAxis: range(
        prices.flatMap((d) => d.ohlc.map((r) => Date.parse(r.date))),
      ),
      yAxis: range(prices.flatMap((d) => d.ohlc.map((r) => r.close))),
    },
  };
}
