import type { HoldingPnL } from "../api/client";
import { formatMoney, formatPercent, pnlColorClass } from "../utils/format";

interface Props {
  ticker: string;
  holding: HoldingPnL | undefined;
}

export function StockPnLCard({ ticker, holding }: Props) {
  if (!holding) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="text-sm text-gray-500">{ticker}</div>
        <div className="mt-1 text-sm text-gray-400">Not held as of this date.</div>
      </div>
    );
  }

  const totalPnl = holding.unrealized_pnl_amount + holding.realized_pnl_sgd;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-sm text-gray-500">{holding.ticker}</div>
      <div className="mt-1 text-2xl font-semibold text-gray-900">
        {formatMoney(holding.price, holding.currency)}
      </div>
      <div className="mt-0.5 text-xs text-gray-400">
        {holding.quantity} sh @ avg {formatMoney(holding.avg_cost, holding.currency)}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-gray-500">Unrealized PnL</div>
          <div className={pnlColorClass(holding.unrealized_pnl_amount)}>
            {formatMoney(holding.unrealized_pnl_amount)}
            <span className="ml-1 text-xs">({formatPercent(holding.unrealized_pnl_pct)})</span>
          </div>
        </div>
        <div>
          <div className="text-gray-500">Realized PnL</div>
          <div className={pnlColorClass(holding.realized_pnl_sgd)}>
            {formatMoney(holding.realized_pnl_sgd)}
          </div>
        </div>
      </div>

      <div className="mt-3 border-t border-gray-100 pt-3 text-sm">
        <div className="text-gray-500">Total PnL</div>
        <div className={`font-medium ${pnlColorClass(totalPnl)}`}>{formatMoney(totalPnl)}</div>
      </div>
    </div>
  );
}
