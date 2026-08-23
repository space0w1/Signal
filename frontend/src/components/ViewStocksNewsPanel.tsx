import { useEffect, useState } from "react";
import { getNewsForStock, type HoldingPnL, type NewsItem } from "../api/client";
import { formatMoney, pnlColorClass } from "../utils/format";
import { NewsList } from "./NewsList";

interface Props {
  holdings: HoldingPnL[];
  date: string;
}

export function ViewStocksNewsPanel({ holdings, date }: Props) {
  const [tab, setTab] = useState<"stocks" | "news">("news");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState<string | null>(null);

  const tickersKey = holdings.map((h) => h.ticker).join(",");

  useEffect(() => {
    if (tab !== "news" || !tickersKey) return;
    const tickers = tickersKey.split(",");

    setNewsLoading(true);
    setNewsError(null);
    Promise.all(tickers.map((ticker) => getNewsForStock(ticker, date)))
      .then((results) => {
        const merged = results.flat().sort((a, b) => {
          const aTime = a.published_at ? new Date(a.published_at).getTime() : 0;
          const bTime = b.published_at ? new Date(b.published_at).getTime() : 0;
          return bTime - aTime;
        });
        setNews(merged);
      })
      .catch((err) => setNewsError(err instanceof Error ? err.message : "Failed to load news"))
      .finally(() => setNewsLoading(false));
  }, [tab, date, tickersKey]);

  return (
    <div className="flex flex-col rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex rounded-lg bg-gray-100 p-1 text-sm font-medium">
        <button
          className={`flex-1 rounded-md py-1.5 ${tab === "news" ? "bg-white shadow-sm" : "text-gray-500"}`}
          onClick={() => setTab("news")}
        >
          News
        </button>
        <button
          className={`flex-1 rounded-md py-1.5 ${tab === "stocks" ? "bg-white shadow-sm" : "text-gray-500"}`}
          onClick={() => setTab("stocks")}
        >
          View Stocks
        </button>
      </div>

      <div className="max-h-[430px] overflow-y-auto">
        {tab === "stocks" ? (
          holdings.length === 0 ? (
            <div className="text-sm text-gray-400">No holdings yet.</div>
          ) : (
            <ul className="space-y-2">
              {holdings.map((h) => {
                const totalPnl = h.unrealized_pnl_amount + h.realized_pnl_sgd;
                return (
                  <li key={h.ticker} className="rounded-lg border border-gray-100 px-3 py-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{h.ticker}</span>
                      <span className={`text-sm font-medium ${pnlColorClass(totalPnl)}`}>
                        {formatMoney(totalPnl)}
                      </span>
                    </div>
                    <div className="mt-0.5 text-xs text-gray-500">
                      {h.quantity} sh @ {formatMoney(h.price, h.currency)}
                    </div>
                  </li>
                );
              })}
            </ul>
          )
        ) : newsLoading ? (
          <div className="text-sm text-gray-400">Loading...</div>
        ) : newsError ? (
          <div className="text-sm text-red-600">{newsError}</div>
        ) : (
          <NewsList
            items={news}
            emptyMessage="No news fetched for your holdings on this date yet."
            showTicker
          />
        )}
      </div>
    </div>
  );
}
