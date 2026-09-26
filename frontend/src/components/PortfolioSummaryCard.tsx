import type { Portfolio } from "../api/client";
import { formatMoney, formatPercent, pnlColorClass } from "../utils/format";

interface Props {
  portfolio: Portfolio;
}

export function PortfolioSummaryCard({ portfolio }: Props) {
  const totalPnl = portfolio.total_unrealized_pnl_amount + portfolio.total_realized_pnl_sgd;

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4 shadow-sm">
      <div className="text-sm text-gray-500 dark:text-gray-400">Portfolio Value</div>
      <div className="mt-1 text-2xl font-semibold text-gray-900 dark:text-gray-100">
        {formatMoney(portfolio.total_value_sgd)}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-gray-500 dark:text-gray-400">Unrealized PnL</div>
          <div className={pnlColorClass(portfolio.total_unrealized_pnl_amount)}>
            {formatMoney(portfolio.total_unrealized_pnl_amount)}
            <span className="ml-1 text-xs">
              ({formatPercent(portfolio.total_unrealized_pnl_pct)})
            </span>
          </div>
        </div>
        <div>
          <div className="text-gray-500 dark:text-gray-400">Realized PnL</div>
          <div className={pnlColorClass(portfolio.total_realized_pnl_sgd)}>
            {formatMoney(portfolio.total_realized_pnl_sgd)}
          </div>
        </div>
      </div>

      <div className="mt-3 border-t border-gray-100 dark:border-gray-800 pt-3 text-sm">
        <div className="text-gray-500 dark:text-gray-400">Total PnL</div>
        <div className={`font-medium ${pnlColorClass(totalPnl)}`}>{formatMoney(totalPnl)}</div>
      </div>
    </div>
  );
}
