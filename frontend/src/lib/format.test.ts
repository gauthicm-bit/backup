import { expect, it } from "vitest";
import { fmtPct, fmtSharpe, fmtDate, fmtDrawdown } from "./format";
it("formats API units for readers (§1.2)", () => {
  expect(fmtPct(0.31)).toBe("31%");
  expect(fmtSharpe(0.842)).toBe("0.84");
  expect(fmtDate("2020-01-31")).toBe("Jan 2020");
  expect(fmtDrawdown(-0.18)).toBe("−18%");
});
