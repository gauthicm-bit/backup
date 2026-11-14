import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CreateAuditRequest } from "../api/types";
const config: CreateAuditRequest = {
  symbol: "^NSEI",
  start: "2010-01-01",
  end: "2025-12-31",
  strategy: {
    template: "ma_crossover",
    grid: { fast: [5, 10, 20, 30], slow: [50, 100, 150, 200] },
  },
  generator: { type: "garch", n_histories: 1000, seed: 42 },
  costs_bps: 5,
  reuse_cached: true,
};
export const useBuilder = create<{
  config: CreateAuditRequest;
  save: (c: CreateAuditRequest) => void;
}>()(
  persist((set) => ({ config, save: (config) => set({ config }) }), {
    name: "multiverse-builder-v1",
  }),
);
