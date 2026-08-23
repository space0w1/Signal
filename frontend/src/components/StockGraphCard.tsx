import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import { getStockGraph, type StockGraphPoint } from "../api/client";
import { formatMoney, pnlColorClass } from "../utils/format";

type ViewMode = "price" | "return";

interface Props {
  ticker: string;
  date: string;
}

export function StockGraphCard({ ticker, date }: Props) {
  const [view, setView] = useState<ViewMode>("price");
  const [points, setPoints] = useState<StockGraphPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getStockGraph(ticker, date)
      .then(setPoints)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph"))
      .finally(() => setLoading(false));
  }, [ticker, date]);

  const currency = points[0]?.currency ?? "USD";
  const returnPoints = points.filter((p) => p.pnl_pct !== null);

  return (
    <div className="flex h-80 flex-col rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-medium text-gray-700">{ticker}</div>
        <div className="flex rounded-lg bg-gray-100 p-1 text-xs font-medium">
          <button
            className={`rounded-md px-3 py-1 ${view === "price" ? "bg-white shadow-sm" : "text-gray-500"}`}
            onClick={() => setView("price")}
          >
            Price
          </button>
          <button
            className={`rounded-md px-3 py-1 ${view === "return" ? "bg-white shadow-sm" : "text-gray-500"}`}
            onClick={() => setView("return")}
          >
            Return
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex flex-1 items-center justify-center text-sm text-gray-400">Loading...</div>
      )}
      {error && <div className="flex flex-1 items-center justify-center text-sm text-red-600">{error}</div>}

      {!loading && !error && (
        <div className="min-h-0 flex-1">
          {view === "price" ? (
            <PriceChart points={points} currency={currency} />
          ) : (
            <ReturnChart points={returnPoints} />
          )}
        </div>
      )}
    </div>
  );
}

function PriceChart({ points, currency }: { points: StockGraphPoint[]; currency: string }) {
  if (points.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        No price data yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="stockFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#2563eb" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
        <YAxis tick={{ fontSize: 11 }} width={55} domain={["auto", "auto"]} />
        <Tooltip formatter={(value) => formatMoney(Number(value ?? 0), currency)} />
        <Area
          type="monotone"
          dataKey="price"
          stroke="#2563eb"
          fill="url(#stockFill)"
          strokeWidth={2}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function ReturnTooltip({ active, payload, label }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload as StockGraphPoint | undefined;
  if (!point) return null;

  return (
    <div className="rounded-md border border-gray-200 bg-white px-3 py-2 text-xs shadow-sm">
      <div className="font-medium text-gray-700">{label}</div>
      {point.pnl_pct !== null && (
        <div className={`mt-1 font-medium ${pnlColorClass(point.pnl_pct)}`}>
          {point.pnl_pct.toFixed(2)}%
        </div>
      )}
      {point.pnl_amount_sgd !== null && (
        <div className={pnlColorClass(point.pnl_amount_sgd)}>{formatMoney(point.pnl_amount_sgd)}</div>
      )}
    </div>
  );
}

function ReturnChart({ points }: { points: StockGraphPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        Not currently held — no return to show.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="returnFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#16a34a" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
        <YAxis tick={{ fontSize: 11 }} width={50} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip content={ReturnTooltip} />
        <Area
          type="monotone"
          dataKey="pnl_pct"
          stroke="#16a34a"
          fill="url(#returnFill)"
          strokeWidth={2}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
