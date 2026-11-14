export const chartTokens = {
  light: {
    accent: "#6153d9",
    text: "#646979",
    grid: "#e9ebef",
    background: "#ffffff",
    neutral: "#a6acb8",
  },
  dark: {
    accent: "#a99cff",
    text: "#9ba3b6",
    grid: "#292d3b",
    background: "#171b27",
    neutral: "#777f91",
  },
};
export function chartTheme(dark = false) {
  const t = chartTokens[dark ? "dark" : "light"];
  return {
    color: [t.accent, t.neutral, "#c8cbd3", "#e2e4e9"],
    backgroundColor: t.background,
    textStyle: { fontFamily: "Inter, system-ui, sans-serif", color: t.text },
    animationDuration: 300,
    animationDurationUpdate: 0,
    grid: { left: 58, right: 24, top: 24, bottom: 50 },
    tooltip: {
      trigger: "axis",
      backgroundColor: t.background,
      borderColor: t.grid,
      textStyle: { color: t.text },
    },
    xAxis: {
      axisLine: { lineStyle: { color: t.grid } },
      axisTick: { show: false },
      axisLabel: { color: t.text },
      splitLine: { show: false },
    },
    yAxis: {
      splitNumber: 5,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: t.text },
      splitLine: { lineStyle: { color: t.grid, width: 1 } },
    },
  };
}
