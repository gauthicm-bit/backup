import { expect, it } from "vitest";
import { range, comparisonRanges } from "./compareRanges";
it("uses joint finite ranges and supports constant / empty series", () => {
  expect(range([1, null, undefined, 8, Infinity])).toEqual({ min: 1, max: 8 });
  expect(range([2, 8], true)).toEqual({ min: 0, max: 8 });
  expect(range([])).toEqual({});
  expect(range([5])).toEqual({ min: 4, max: 6 });
  expect(comparisonRanges([]).pbo.xAxis).toEqual({ min: -6, max: 6 });
});
