import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getSectorFlowHistory,
  getSectorFlows,
  type SectorFlow,
  type SectorFlowPoint,
  type SectorPeriod,
} from "../api/client";
import type { Theme } from "../theme";
import { formatPercent, formatUsdCompact, pnlColorClass } from "../utils/format";
import { divergingColor } from "../utils/worldColors";

const PERIODS: { value: SectorPeriod; label: string }[] = [
  { value: "1d", label: "1D" },
  { value: "1w", label: "1W" },
  { value: "1m", label: "1M" },
  { value: "ytd", label: "YTD" },
];

// A net flow of this size (as % of the fund's assets) or more gets the strongest colour, per period.
const FLOW_PCT_SCALE: Record<SectorPeriod, number> = { "1d": 1, "1w": 3, "1m": 6, ytd: 15 };

function flowColor(flowPct: number | null, period: SectorPeriod, dark: boolean): string {
  return flowPct === null ? "transparent" : divergingColor(flowPct / FLOW_PCT_SCALE[period], dark);
}

function PeriodToggle({ period, onChange }: { period: SectorPeriod; onChange: (p: SectorPeriod) => void }) {
  return (
    <div className="flex rounded-lg bg-gray-100 p-1 text-xs font-medium dark:bg-gray-800">
      {PERIODS.map((p) => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          className={`rounded-md px-3 py-1 ${
            period === p.value ? "bg-white shadow-sm dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 dark:text-gray-400"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

function FlowBars({
  sectors,
  period,
  dark,
  selected,
  onSelect,
}: {
  sectors: SectorFlow[];
  period: SectorPeriod;
  dark: boolean;
  selected: string | null;
  onSelect: (symbol: string) => void;
}) {
  const data = useMemo(
    () =>
      sectors
        .filter((s) => s.periods[period].flow !== null)
        .map((s) => ({ symbol: s.symbol, label: s.name, ...s.periods[period] }))
        .sort((a, b) => (b.flow ?? 0) - (a.flow ?? 0)),
    [sectors, period],
  );
  const axisColor = dark ? "#9ca3af" : "#6b7280";

  return (
    <ResponsiveContainer width="100%" height={360}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke={dark ? "#1f2937" : "#f0f0f0"} />
        <XAxis
          type="number"
          tick={{ fontSize: 11, fill: axisColor }}
          tickFormatter={(v) => formatUsdCompact(Number(v))}
        />
        <YAxis type="category" dataKey="label" width={170} tick={{ fontSize: 12, fill: axisColor }} interval={0} />
        <ReferenceLine x={0} stroke={axisColor} />
        <Tooltip
          cursor={{ fill: dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)" }}
          contentStyle={{
            background: dark ? "#111827" : "#fff",
            border: `1px solid ${dark ? "#374151" : "#e5e7eb"}`,
            borderRadius: 6,
            fontSize: 12,
          }}
          formatter={(value, _name, item) => {
            const pct = (item.payload as { flow_pct: number | null }).flow_pct;
            return [
              `${formatUsdCompact(Number(value), true)}${pct === null ? "" : ` (${formatPercent(pct)} of assets)`}`,
              "Net flow",
            ];
          }}
        />
        <Bar dataKey="flow" radius={3} onClick={(entry) => onSelect((entry as unknown as { symbol: string }).symbol)}>
          {data.map((d) => (
            <Cell
              key={d.symbol}
              cursor="pointer"
              fill={flowColor(d.flow_pct, period, dark)}
              stroke={d.symbol === selected ? (dark ? "#f9fafb" : "#111827") : undefined}
              strokeWidth={d.symbol === selected ? 1.5 : 0}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function FlowGrid({
  sectors,
  period,
  dark,
  selected,
  onSelect,
}: {
  sectors: SectorFlow[];
  period: SectorPeriod;
  dark: boolean;
  selected: string | null;
  onSelect: (symbol: string) => void;
}) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs text-gray-500 dark:text-gray-400">
          <th className="px-2 py-1.5 text-left font-medium">Sector</th>
          {PERIODS.map((p) => (
            <th
              key={p.value}
              className={`px-2 py-1.5 text-right font-medium ${p.value === period ? "text-gray-900 dark:text-gray-100" : ""}`}
            >
              {p.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sectors.map((s) => (
          <tr
            key={s.symbol}
            onClick={() => onSelect(s.symbol)}
            className={`cursor-pointer ${s.symbol === selected ? "bg-gray-100 dark:bg-gray-800" : "hover:bg-gray-50 dark:hover:bg-gray-800/60"}`}
          >
            <td className="px-2 py-1 text-gray-700 dark:text-gray-300">
              {s.name}
              <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">{s.symbol}</span>
            </td>
            {PERIODS.map((p) => {
              const { flow, flow_pct } = s.periods[p.value];
              const strong = flow_pct !== null && Math.abs(flow_pct) / FLOW_PCT_SCALE[p.value] > 0.5;
              return (
                <td key={p.value} className="px-1 py-0.5">
                  <div
                    className={`rounded px-2 py-1 text-right font-medium tabular-nums ${
                      strong ? "text-white" : "text-gray-800 dark:text-gray-100"
                    } ${p.value === period ? "ring-1 ring-gray-400 dark:ring-gray-500" : ""}`}
                    style={{ background: flowColor(flow_pct, p.value, dark) }}
                    title={flow_pct === null ? undefined : `${formatPercent(flow_pct)} of assets`}
                  >
                    {flow === null ? "—" : formatUsdCompact(flow, true)}
                  </div>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SectorDetail({ sector, dark }: { sector: SectorFlow; dark: boolean }) {
  const [history, setHistory] = useState<SectorFlowPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    getSectorFlowHistory(sector.symbol)
      .then(setHistory)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load flow history"));
  }, [sector.symbol]);

  const end = history[history.length - 1]?.cumulative_flow ?? 0;
  const lineColor = end >= 0 ? "#16a34a" : "#dc2626";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
      <div className="text-sm font-medium text-gray-700 dark:text-gray-300">{sector.name}</div>
      <div className="mt-1 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span>{sector.symbol} · NAV {sector.nav?.toFixed(2) ?? "—"}</span>
        {sector.stale && <span className="text-amber-600 dark:text-amber-400">stale</span>}
      </div>
      <div className="mt-3 text-2xl font-semibold text-gray-900 dark:text-gray-100">
        {sector.total_net_assets === null ? "—" : formatUsdCompact(sector.total_net_assets)}
        <span className="ml-1 text-sm font-normal text-gray-500">in the fund</span>
      </div>
      <div className="text-xs text-gray-400 dark:text-gray-500">as of {sector.as_of ?? "—"}</div>

      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
        {PERIODS.map((p) => {
          const { flow, change } = sector.periods[p.value];
          return (
            <div key={p.value} className="rounded-lg bg-gray-100 py-1.5 dark:bg-gray-800">
              <div className="text-xs text-gray-500 dark:text-gray-400">{p.label}</div>
              <div className={`text-sm font-medium ${flow === null ? "text-gray-400" : pnlColorClass(flow)}`}>
                {flow === null ? "—" : formatUsdCompact(flow, true)}
              </div>
              <div className={`text-xs ${change === null ? "text-gray-400" : pnlColorClass(change)}`}>
                {change === null ? "—" : formatPercent(change)}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-1 text-right text-[11px] text-gray-400 dark:text-gray-500">net flow / price change</div>

      <div className="mt-4 text-xs font-medium text-gray-600 dark:text-gray-400">Cumulative net flow, past year</div>
      {error ? (
        <div className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</div>
      ) : (
        <div className="h-36">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="sectorFlowFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={lineColor} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={lineColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" hide />
              <YAxis
                width={52}
                tick={{ fontSize: 10, fill: dark ? "#9ca3af" : "#6b7280" }}
                tickFormatter={(v) => formatUsdCompact(Number(v))}
              />
              <ReferenceLine y={0} stroke={dark ? "#4b5563" : "#d1d5db"} />
              <Tooltip
                contentStyle={{
                  background: dark ? "#111827" : "#fff",
                  border: `1px solid ${dark ? "#374151" : "#e5e7eb"}`,
                  borderRadius: 6,
                  fontSize: 12,
                }}
                formatter={(value) => [formatUsdCompact(Number(value), true), "Since start"]}
              />
              <Area type="monotone" dataKey="cumulative_flow" stroke={lineColor} fill="url(#sectorFlowFill)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default function SectorsPage({ theme }: { theme: Theme }) {
  const [sectors, setSectors] = useState<SectorFlow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<SectorPeriod>("1m");
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const dark = theme === "dark";

  useEffect(() => {
    getSectorFlows()
      .then(setSectors)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load sector flows"))
      .finally(() => setLoading(false));
  }, []);

  const selected = sectors.find((s) => s.symbol === selectedSymbol);
  const latestDate = sectors.reduce<string | null>((d, s) => (s.as_of && (!d || s.as_of > d) ? s.as_of : d), null);
  const inflow = sectors.filter((s) => (s.periods[period].flow ?? 0) > 0);
  const outflow = sectors.filter((s) => (s.periods[period].flow ?? 0) < 0);
  const sum = (list: SectorFlow[]) => list.reduce((t, s) => t + (s.periods[period].flow ?? 0), 0);

  return (
    <>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Sector flows</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Net money investors put into (+) or pulled out of (−) each US sector ETF, from daily changes in shares outstanding
            {latestDate && (
              <>
                {" · as of "}
                <span className="font-semibold text-gray-700 dark:text-gray-300">{latestDate}</span>
              </>
            )}
          </p>
        </div>
        <PeriodToggle period={period} onChange={setPeriod} />
      </div>

      {loading && <div className="text-sm text-gray-500 dark:text-gray-400">Loading...</div>}
      {error && <div className="text-sm text-red-600 dark:text-red-400">{error}</div>}

      {!loading && !error && (
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 flex flex-col gap-4">
            <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
              <div className="mb-2 flex items-baseline justify-between text-sm">
                <span className="font-medium text-gray-700 dark:text-gray-300">
                  Net flows, {PERIODS.find((p) => p.value === period)?.label}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  <span className="text-emerald-600 dark:text-emerald-400">{formatUsdCompact(sum(inflow), true)}</span> into{" "}
                  {inflow.length} · <span className="text-red-600 dark:text-red-400">{formatUsdCompact(sum(outflow))}</span> out
                  of {outflow.length}
                </span>
              </div>
              <FlowBars sectors={sectors} period={period} dark={dark} selected={selectedSymbol} onSelect={setSelectedSymbol} />
              <p className="mt-2 text-[11px] text-gray-400 dark:text-gray-500">
                Colour shows the flow relative to the fund's size, so a small fund with a big inflow stands out as much as a large one.
              </p>
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
              <div className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">Short run vs long run</div>
              <FlowGrid sectors={sectors} period={period} dark={dark} selected={selectedSymbol} onSelect={setSelectedSymbol} />
            </div>
          </div>

          <div className="flex flex-col gap-4">
            {selected ? (
              <SectorDetail sector={selected} dark={dark} />
            ) : (
              <div className="rounded-xl border border-dashed border-gray-200 p-4 text-sm text-gray-400 dark:border-gray-700 dark:text-gray-500">
                Click a sector for its fund size, price moves and a year of cumulative flows.
              </div>
            )}
            <div className="rounded-xl border border-gray-200 bg-white p-4 text-xs leading-relaxed text-gray-500 shadow-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
              <div className="mb-1 font-medium text-gray-700 dark:text-gray-300">Reading this</div>
              When investors put net money into an ETF it creates new shares; when they pull money out, shares are redeemed. Flow is the
              change in shares × NAV. State Street often reports creations a day late, so a 1D figure can belong to the previous session.
            </div>
          </div>
        </div>
      )}
    </>
  );
}
