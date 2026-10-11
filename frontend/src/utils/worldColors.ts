import type { WorldPeriod } from "../api/client";

// A move of this size (in %) or more gets the strongest colour, per period.
export const COLOR_SCALE: Record<WorldPeriod, number> = {
  change_1d: 2,
  change_1w: 5,
  change_1m: 10,
  change_ytd: 30,
};

type Rgb = [number, number, number];
const UP: Rgb = [22, 163, 74]; // green-600
const DOWN: Rgb = [220, 38, 38]; // red-600

export function palette(dark: boolean) {
  return {
    ocean: dark ? "#0b1220" : "#dbeafe",
    untracked: dark ? "#1f2937" : "#f3f4f6",
    neutral: (dark ? [75, 85, 99] : [209, 213, 219]) as Rgb, // tracked market, ~0% change
    stroke: dark ? "#111827" : "#9ca3af",
    side: dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.08)",
    atmosphere: dark ? "#3b82f6" : "#93c5fd",
  };
}

export function changeColor(change: number | null, period: WorldPeriod, dark: boolean): string {
  const { untracked } = palette(dark);
  if (change === null) return untracked;
  return divergingColor(change / COLOR_SCALE[period], dark);
}

// t in [-1, 1] (clamped): red through neutral grey to green. Shared with the Sectors page.
export function divergingColor(t: number, dark: boolean): string {
  const { neutral } = palette(dark);
  t = Math.max(-1, Math.min(1, t));
  const target = t >= 0 ? UP : DOWN;
  const [r, g, b] = neutral.map((n, i) => Math.round(n + (target[i] - n) * Math.abs(t)));
  return `rgb(${r}, ${g}, ${b})`;
}
