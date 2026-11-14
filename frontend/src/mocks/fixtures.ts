import type {
  TemplateInfo,
  GeneratorInfo,
  CreateAuditRequest,
  Preset,
} from "../api/types";
const param = (
  name: string,
  label: string,
  min: number,
  max: number,
  values: number[],
  type: "int" | "float" = "int",
  step = 1,
) => ({ name, label, min, max, default_values: values, type, step });
export const templates: TemplateInfo[] = [
  {
    id: "ma_crossover",
    name: "Moving average crossover",
    description:
      "Follow persistent trends with a fast and slow moving average.",
    params: [
      param("fast", "Fast window", 2, 100, [5, 10, 20, 30]),
      param("slow", "Slow window", 10, 300, [50, 100, 150, 200]),
    ],
    constraints: [{ left: "fast", op: "<", right: "slow" }],
    default_grid: { fast: [5, 10, 20, 30], slow: [50, 100, 150, 200] },
    default_n_variants: 16,
  },
  {
    id: "momentum",
    name: "Momentum",
    description: "Enter when trailing returns exceed a threshold.",
    params: [
      param("lookback", "Lookback days", 5, 252, [20, 60, 120, 252]),
      param(
        "threshold",
        "Return threshold",
        -0.05,
        0.1,
        [0, 0.02, 0.05],
        "float",
        0.005,
      ),
    ],
    constraints: [],
    default_grid: { lookback: [20, 60, 120, 252], threshold: [0, 0.02, 0.05] },
    default_n_variants: 12,
  },
  {
    id: "rsi_mean_reversion",
    name: "RSI mean reversion",
    description: "Buy oversold conditions and exit on recovery.",
    params: [
      param("period", "RSI period", 2, 30, [7, 14]),
      param("entry", "Entry RSI", 5, 45, [20, 30]),
      param("exit", "Exit RSI", 50, 95, [55, 70]),
    ],
    constraints: [{ left: "entry", op: "<", right: "exit" }],
    default_grid: { period: [7, 14], entry: [20, 30], exit: [55, 70] },
    default_n_variants: 8,
  },
  {
    id: "breakout",
    name: "Price breakout",
    description: "Follow closes above the prior range.",
    params: [
      param("entry_lookback", "Entry lookback", 10, 252, [20, 55, 100, 200]),
      param("exit_lookback", "Exit lookback", 5, 126, [10, 20]),
    ],
    constraints: [{ left: "exit_lookback", op: "<=", right: "entry_lookback" }],
    default_grid: {
      entry_lookback: [20, 55, 100, 200],
      exit_lookback: [10, 20],
    },
    default_n_variants: 8,
  },
];
export const defaultConfig: CreateAuditRequest = {
  symbol: "^NSEI",
  start: "2010-01-01",
  end: "2025-12-31",
  strategy: { template: "ma_crossover", grid: templates[0].default_grid },
  generator: { type: "garch", n_histories: 1000, seed: 42 },
  costs_bps: 5,
  reuse_cached: true,
};
export const generators: GeneratorInfo[] = [
  {
    id: "garch",
    name: "GJR-GARCH",
    description:
      "Student-t innovations with asymmetric volatility. Fitted to your date range.",
    available: true,
    trained: true,
    realism_passed: null,
    trained_on: null,
  },
  {
    id: "timegan",
    name: "TimeGAN",
    description: "A deep generative challenger.",
    available: false,
    trained: false,
    realism_passed: null,
    trained_on: null,
  },
  {
    id: "diffusion",
    name: "Diffusion",
    description: "A future challenger for synthetic market paths.",
    available: false,
    trained: false,
    realism_passed: null,
    trained_on: null,
  },
];
export const presets: Preset[] = [
  {
    id: "overfit",
    name: "The overfit strategy",
    description:
      "A crowded parameter search. Does the winning backtest survive?",
    config: {
      ...defaultConfig,
      generator: { ...defaultConfig.generator, n_histories: 100 },
    },
    cached_audit_id: null,
  },
  {
    id: "robust",
    name: "The robust candidate",
    description: "A slower trend strategy tested over a longer history.",
    config: {
      ...defaultConfig,
      strategy: {
        template: "ma_crossover",
        grid: { fast: [20, 30], slow: [150, 200] },
      },
    },
    cached_audit_id: null,
  },
];
