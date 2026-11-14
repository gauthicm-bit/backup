export const fmtPct = (n: number, digits = 0) =>
  new Intl.NumberFormat("en-IN", {
    style: "percent",
    maximumFractionDigits: digits,
  }).format(n);
export const fmtSharpe = (n: number) => n.toFixed(2);
export const fmtDate = (date: string) =>
  new Intl.DateTimeFormat("en-GB", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date.slice(0, 10)}T00:00:00Z`));
export const fmtDrawdown = (n: number) =>
  `${n < 0 ? "−" : ""}${fmtPct(Math.abs(n))}`;
export const fmtRupees = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(n);
