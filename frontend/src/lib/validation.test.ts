import { describe, expect, it } from "vitest";
import { expandGrid, validateAudit, parseValues } from "./validation";
import { templates, defaultConfig } from "../mocks/fixtures";
describe("contract §5.6 builder validation", () => {
  it("expands defaults in contract order", () => {
    expect(templates.map((t) => expandGrid(t, t.default_grid).length)).toEqual([
      16, 12, 8, 8,
    ]);
  });
  it("sorts values and excludes invalid constraints", () => {
    expect(expandGrid(templates[0], { fast: [20, 5], slow: [10, 50] })).toEqual(
      [
        { fast: 5, slow: 10 },
        { fast: 5, slow: 50 },
        { fast: 20, slow: 50 },
      ],
    );
  });
  it("rejects duplicate, out-of-range and fractional integer values", () => {
    for (const fast of [[5, 5], [101], [5.2]])
      expect(() =>
        expandGrid(templates[0], { fast, slow: [50, 100] }),
      ).toThrow();
  });
  it("rejects malformed numeric tokens", () => {
    expect(() => parseValues("5, nope")).toThrow();
    expect(() => parseValues("5,,10")).toThrow();
  });
  it("validates dates and at least two variants", () => {
    expect(validateAudit(defaultConfig, templates[0]).success).toBe(true);
    expect(
      validateAudit({ ...defaultConfig, start: "2025-01-01" }, templates[0])
        .success,
    ).toBe(false);
    expect(
      validateAudit(
        {
          ...defaultConfig,
          strategy: {
            template: "ma_crossover",
            grid: { fast: [5], slow: [50] },
          },
        },
        templates[0],
      ).success,
    ).toBe(false);
  });
});
