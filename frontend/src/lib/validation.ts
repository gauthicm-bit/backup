import { z } from "zod";
import type { CreateAuditRequest, TemplateInfo } from "../api/types";
export function parseValues(text: string): number[] {
  const tokens = text.split(",").map((t) => t.trim());
  if (tokens.some((t) => !t || !Number.isFinite(Number(t))))
    throw new Error("Enter numbers separated by commas.");
  return tokens.map(Number);
}
export function expandGrid(
  template: TemplateInfo,
  grid: Record<string, number[]>,
): Record<string, number>[] {
  if (
    Object.keys(grid).sort().join() !==
    template.params
      .map((p) => p.name)
      .sort()
      .join()
  )
    throw new Error("Provide every strategy parameter.");
  let variants: Record<string, number>[] = [{}];
  for (const p of template.params) {
    const values = grid[p.name];
    if (
      values.length < 1 ||
      values.length > 10 ||
      new Set(values).size !== values.length ||
      values.some(
        (v) =>
          !Number.isFinite(v) ||
          v < p.min ||
          v > p.max ||
          (p.type === "int" && !Number.isInteger(v)),
      )
    )
      throw new Error(
        `${p.label}: enter 1–10 unique ${p.type === "int" ? "whole " : ""}numbers from ${p.min} to ${p.max}.`,
      );
    variants = variants.flatMap((v) =>
      [...values].sort((a, b) => a - b).map((n) => ({ ...v, [p.name]: n })),
    );
  }
  return variants.filter((v) =>
    template.constraints.every((c) =>
      c.op === "<" ? v[c.left] < v[c.right] : v[c.left] <= v[c.right],
    ),
  );
}
export function validateAudit(
  config: CreateAuditRequest,
  template: TemplateInfo,
) {
  const schema = z
    .object({
      start: z.iso.date(),
      end: z.iso.date(),
      costs_bps: z.number().min(0).max(100),
      generator: z.object({
        type: z.enum(["garch", "timegan", "diffusion"]),
        n_histories: z.union([
          z.literal(100),
          z.literal(500),
          z.literal(1000),
          z.literal(5000),
        ]),
        seed: z.number().int().min(0).max(2147483647),
      }),
    })
    .superRefine((v, ctx) => {
      const anniversary = new Date(`${v.start}T00:00:00Z`);
      anniversary.setUTCFullYear(anniversary.getUTCFullYear() + 3);
      const today = new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Kolkata",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(new Date());
      if (
        v.start < "2008-01-01" ||
        v.end > today ||
        new Date(`${v.end}T00:00:00Z`) < anniversary
      )
        ctx.addIssue({
          code: "custom",
          path: ["start"],
          message:
            "Choose at least three years, starting in 2008 or later and ending no later than today.",
        });
      try {
        const n = expandGrid(template, config.strategy.grid).length;
        if (n < 2 || n > 64)
          throw new Error("Use between 2 and 64 valid variants.");
      } catch (e) {
        ctx.addIssue({
          code: "custom",
          path: ["strategy", "grid"],
          message: (e as Error).message,
        });
      }
    });
  return schema.safeParse(config);
}
