import { useEffect, useRef, useContext } from "react";
import { CompareRanges } from "../lib/compareRanges";
import {
  AreaSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  type Time,
} from "lightweight-charts";
import type { OHLCRow } from "../api/types";
export default function PriceChart({
  rows,
  signals = [],
}: {
  rows: OHLCRow[];
  signals?: { date: string; side: "buy" | "sell"; price: number }[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const shared = useContext(CompareRanges).price;
  const rangeKey = JSON.stringify(shared);
  const signalKey = JSON.stringify(signals);
  useEffect(() => {
    if (!ref.current || !rows.length) return;
    const chart = createChart(ref.current, {
      autoSize: true,
      height: 285,
      layout: {
        background: { type: ColorType.Solid, color: "#fff" },
        textColor: "#8a8f9d",
        fontFamily: "Inter, system-ui, sans-serif",
      },
      grid: { vertLines: { visible: false }, horzLines: { color: "#f0f1f5" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, minBarSpacing: 0.01 },
      crosshair: {
        vertLine: { color: "#b6aecf" },
        horzLine: { color: "#b6aecf" },
      },
    });
    const ranges = JSON.parse(rangeKey || "{}") as typeof shared;
    const series = chart.addSeries(AreaSeries, {
      lineColor: "#7565dc",
      topColor: "rgba(117,101,220,.16)",
      bottomColor: "rgba(117,101,220,0)",
      lineWidth: 2,
      autoscaleInfoProvider:
        ranges?.yAxis?.min !== undefined && ranges?.yAxis?.max !== undefined
          ? () => ({
              priceRange: {
                minValue: ranges.yAxis!.min!,
                maxValue: ranges.yAxis!.max!,
              },
            })
          : undefined,
      priceFormat: {
        type: "custom",
        formatter: (p: number) => `₹${Math.round(p).toLocaleString("en-IN")}`,
      },
    });
    const data: ({ time: Time; value: number } | { time: Time })[] = rows.map(
      (r) => ({ time: r.date as Time, value: r.close }),
    );
    if (ranges?.xAxis?.min !== undefined && ranges?.xAxis?.max !== undefined) {
      const first = new Date(ranges.xAxis.min).toISOString().slice(0, 10),
        last = new Date(ranges.xAxis.max).toISOString().slice(0, 10);
      if (first < rows[0].date) data.unshift({ time: first as Time });
      if (last > rows.at(-1)!.date) data.push({ time: last as Time });
    }
    series.setData(data);
    const markerSignals = JSON.parse(signalKey) as typeof signals;
    createSeriesMarkers(
      series,
      markerSignals.map((s) => ({
        time: s.date as Time,
        position: s.side === "buy" ? "belowBar" : "aboveBar",
        shape: s.side === "buy" ? "arrowUp" : "arrowDown",
        color: s.side === "buy" ? "#7565dc" : "#8d94a1",
        text: s.side === "buy" ? "Buy" : "Sell",
      })),
    );
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [rows, signalKey, rangeKey]);
  return (
    <div
      ref={ref}
      role="img"
      aria-label="Nifty 50 closing prices"
      className="price-canvas"
    />
  );
}
