import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getStockGraph, type StockPricePoint } from "../api/client";
import { formatMoney } from "../utils/format";

interface Props {
  ticker: string;
  date: string;
}

export function StockGraphCard({ ticker, date }: Props) {
  const [points, setPoints] = useState<StockPricePoint[]>([]);
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

  return (
    <div className="flex h-80 flex-col rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-2 text-sm font-medium text-gray-700">{ticker} — Price</div>

      {loading && (
        <div className="flex flex-1 items-center justify-center text-sm text-gray-400">Loading...</div>
      )}
      {error && <div className="flex flex-1 items-center justify-center text-sm text-red-600">{error}</div>}

      {!loading && !error && (
        <div className="min-h-0 flex-1">
          {points.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-gray-400">
              No price data yet.
            </div>
          ) : (
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
          )}
        </div>
      )}
    </div>
  );
}
