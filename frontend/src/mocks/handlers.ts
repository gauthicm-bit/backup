import { http, HttpResponse } from "msw";
import { templates, generators, presets } from "./fixtures";
import type { AuditDetail, CreateAuditRequest } from "../api/types";
import { expandGrid } from "../lib/validation";
const audits = new Map<string, AuditDetail>();
const base = "*/api/v1";
const notFound = () =>
  HttpResponse.json(
    {
      error: {
        code: "audit_not_found",
        message: "Audit not found.",
        details: null,
      },
    },
    { status: 404 },
  );
export const handlers = [
  http.get(`${base}/health`, () =>
    HttpResponse.json({
      status: "ok",
      redis: "ok",
      db: "ok",
      job_mode: "inprocess",
      contract_version: "1.0.0",
    }),
  ),
  http.get(`${base}/strategies/templates`, () => HttpResponse.json(templates)),
  http.get(`${base}/generators`, () => HttpResponse.json(generators)),
  http.get(`${base}/presets`, () => HttpResponse.json(presets)),
  http.get(`${base}/market/prices`, ({ request }) => {
    const u = new URL(request.url);
    const start = u.searchParams.get("start")!,
      end = u.searchParams.get("end")!;
    const date = new Date(`${start}T00:00:00Z`),
      ohlc = [];
    let i = 0;
    while (date.toISOString().slice(0, 10) <= end) {
      if (date.getUTCDay() > 0 && date.getUTCDay() < 6) {
        const close =
          5000 *
          Math.exp(
            i * 0.0003 + Math.sin(i / 70) * 0.1 + Math.sin(i / 13) * 0.015,
          );
        ohlc.push({
          date: date.toISOString().slice(0, 10),
          open: close * 0.999,
          high: close * 1.005,
          low: close * 0.995,
          close,
          volume: null,
        });
        i++;
      }
      date.setUTCDate(date.getUTCDate() + 1);
    }
    return HttpResponse.json({
      symbol: "^NSEI",
      start,
      end,
      source: "cache",
      fetched_at: "2026-11-14T09:00:00Z",
      ohlc,
    });
  }),
  http.post(`${base}/audits`, async ({ request }) => {
    const config = (await request.json()) as CreateAuditRequest;
    const id = `aud_01JCX8Q6T3W9K2M4N5P7R8S${String(audits.size).padStart(3, "0")}`;
    const variants = expandGrid(
      templates.find((t) => t.id === config.strategy.template)!,
      config.strategy.grid,
    );
    audits.set(id, {
      id,
      status: "queued",
      created_at: new Date().toISOString(),
      started_at: null,
      finished_at: null,
      config,
      derived: {
        n_trials: variants.length,
        variants,
        selected_variant: null,
        config_hash: "mock",
        versions: { app: "2.2.0" },
      },
      verdict: null,
      headline: null,
      metrics: null,
      thresholds: {
        pbo_skill_max: 0.25,
        dsr_skill_min: 0.95,
        survival_skill_min: 0.6,
        pbo_luck_min: 0.5,
        dsr_luck_max: 0.5,
      },
      progress: { stage: "fetch", pct: 0, message: "Fetching market history" },
      error: null,
    });
    return HttpResponse.json(
      { audit_id: id, status: "queued", cached: false },
      { status: 202 },
    );
  }),
  http.get(`${base}/audits/:id/events`, ({ params }) => {
    if (!audits.has(String(params.id))) return notFound();
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        for (const stage of ["fetch", "simulate", "backtest", "metrics"]) {
          controller.enqueue(
            encoder.encode(
              `event: progress\ndata: ${JSON.stringify({ stage, pct: 100, message: `${stage} complete`, ts: new Date().toISOString() })}\n\n`,
            ),
          );
          await new Promise((r) => setTimeout(r, 250));
        }
        controller.enqueue(
          encoder.encode(
            'event: error\ndata: {"code":"demo_only","message":"Mock progress complete. Start the real backend to calculate an audit."}\n\n',
          ),
        );
        controller.close();
      },
    });
    return new HttpResponse(stream, {
      headers: { "Content-Type": "text/event-stream" },
    });
  }),
  http.get(`${base}/audits/:id`, ({ params }) =>
    audits.has(String(params.id))
      ? HttpResponse.json(audits.get(String(params.id)))
      : notFound(),
  ),
  http.get(`${base}/audits`, () =>
    HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
  ),
];
