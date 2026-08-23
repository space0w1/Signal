import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getPortfolioGraph,
  type AggregatePoint,
  type GraphMode,
  type OverlayPoint,
} from "../api/client";
import { formatMoney } from "../utils/format";

const LINE_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#d97706", "#0891b2"];
const PORTFOLIO_LINE_KEY = "Portfolio";

interface Props {
  date: string;
}

export function PortfolioGraphCard({ date }: Props) {
  const [mode, setMode] = useState<GraphMode>("aggregate");
  const [aggregate, setAggregate] = useState<AggregatePoint[]>([]);
  const [overlay, setOverlay] = useState<Record<string, OverlayPoint[]>>({});
  const [overlayPortfolio, setOverlayPortfolio] = useState<OverlayPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getPortfolioGraph(date, mode)
      .then((data) => {
        setAggregate(data.aggregate ?? []);
        setOverlay(data.overlay ?? {});
        setOverlayPortfolio(data.overlay_portfolio ?? []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph"))
      .finally(() => setLoading(false));
  }, [date, mode]);

  return (
    <div className="flex h-80 flex-col rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-medium text-gray-700">Portfolio Graph</div>
        <div className="flex rounded-lg bg-gray-100 p-1 text-xs font-medium">
          <button
            className={`rounded-md px-3 py-1 ${mode === "aggregate" ? "bg-white shadow-sm" : "text-gray-500"}`}
            onClick={() => setMode("aggregate")}
          >
            Value
          </button>
          <button
            className={`rounded-md px-3 py-1 ${mode === "overlay" ? "bg-white shadow-sm" : "text-gray-500"}`}
            onClick={() => setMode("overlay")}
          >
            Returns
          </button>
        </div>
      </div>

      {loading && <div className="flex flex-1 items-center justify-center text-sm text-gray-400">Loading...</div>}
      {error && <div className="flex flex-1 items-center justify-center text-sm text-red-600">{error}</div>}

      {!loading && !error && (
        <div className="min-h-0 flex-1">
          {mode === "aggregate" ? (
            <AggregateChart points={aggregate} />
          ) : (
            <OverlayChart series={overlay} portfolio={overlayPortfolio} />
          )}
        </div>
      )}
    </div>
  );
}

function AggregateChart({ points }: { points: AggregatePoint[] }) {
  if (points.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        No holdings yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="valueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#2563eb" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
        <YAxis
          tick={{ fontSize: 11 }}
          width={60}
          tickFormatter={(v: number) => `$${Math.round(v / 1000)}k`}
        />
        <Tooltip formatter={(value) => formatMoney(Number(value ?? 0))} />
        <Area
          type="monotone"
          dataKey="total_value_sgd"
          stroke="#2563eb"
          fill="url(#valueFill)"
          strokeWidth={2}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function OverlayChart({
  series,
  portfolio,
}: {
  series: Record<string, OverlayPoint[]>;
  portfolio: OverlayPoint[];
}) {
  const tickers = useMemo(() => Object.keys(series), [series]);

  const rows = useMemo(() => {
    const dateSet = new Set<string>();
    for (const points of Object.values(series)) {
      for (const p of points) dateSet.add(p.date);
    }
    for (const p of portfolio) dateSet.add(p.date);
    const dates = Array.from(dateSet).sort();

    const lookups = tickers.map((t) => new Map(series[t].map((p) => [p.date, p.pnl_pct])));
    const portfolioLookup = new Map(portfolio.map((p) => [p.date, p.pnl_pct]));

    return dates.map((date) => {
      const row: Record<string, string | number | null> = { date };
      tickers.forEach((ticker, i) => {
        row[ticker] = lookups[i].get(date) ?? null;
      });
      row[PORTFOLIO_LINE_KEY] = portfolioLookup.get(date) ?? null;
      return row;
    });
  }, [series, tickers, portfolio]);

  if (tickers.length === 0 && portfolio.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        No active holdings yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
        <YAxis tick={{ fontSize: 11 }} width={50} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip formatter={(value) => `${Number(value ?? 0).toFixed(2)}%`} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {tickers.map((ticker, i) => (
          <Line
            key={ticker}
            type="monotone"
            dataKey={ticker}
            stroke={LINE_COLORS[i % LINE_COLORS.length]}
            strokeWidth={1.5}
            dot={false}
            connectNulls={false}
            strokeOpacity={0.6}
          />
        ))}
        <Line
          type="monotone"
          dataKey={PORTFOLIO_LINE_KEY}
          stroke="#111827"
          strokeWidth={3}
          dot={false}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
