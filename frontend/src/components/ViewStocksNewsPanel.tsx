import { useState } from "react";
import type { HoldingPnL } from "../api/client";
import { formatMoney, pnlColorClass } from "../utils/format";

interface Props {
  holdings: HoldingPnL[];
}

export function ViewStocksNewsPanel({ holdings }: Props) {
  const [tab, setTab] = useState<"stocks" | "news">("stocks");

  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex rounded-lg bg-gray-100 p-1 text-sm font-medium">
        <button
          className={`flex-1 rounded-md py-1.5 ${tab === "stocks" ? "bg-white shadow-sm" : "text-gray-500"}`}
          onClick={() => setTab("stocks")}
        >
          View Stocks
        </button>
        <button
          className={`flex-1 rounded-md py-1.5 ${tab === "news" ? "bg-white shadow-sm" : "text-gray-500"}`}
          onClick={() => setTab("news")}
        >
          News
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
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
        ) : (
          <div className="text-sm text-gray-400">News feed coming soon.</div>
        )}
      </div>
    </div>
  );
}
