import { useEffect, useState } from "react";
import { getNewsForStock, type NewsItem } from "../api/client";
import { NewsList } from "./NewsList";

interface Props {
  ticker: string;
  date: string;
}

export function StockNewsPanel({ ticker, date }: Props) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getNewsForStock(ticker, date)
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load news"))
      .finally(() => setLoading(false));
  }, [ticker, date]);

  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 text-sm font-medium text-gray-700">News</div>
      <div className="flex-1 overflow-y-auto">
        {loading && <div className="text-sm text-gray-400">Loading...</div>}
        {error && <div className="text-sm text-red-600">{error}</div>}
        {!loading && !error && (
          <NewsList items={items} emptyMessage="No news fetched for this date yet." />
        )}
      </div>
    </div>
  );
}
