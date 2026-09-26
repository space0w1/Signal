import { useCallback, useEffect, useState } from "react";
import { getPortfolio, type Portfolio } from "./api/client";
import { TopBar, PORTFOLIO_OPTION } from "./components/TopBar";
import { PortfolioSummaryCard } from "./components/PortfolioSummaryCard";
import { ViewStocksNewsPanel } from "./components/ViewStocksNewsPanel";
import { ModifyPortfolioModal } from "./components/ModifyPortfolioModal";
import { PortfolioGraphCard } from "./components/PortfolioGraphCard";
import { StockGraphCard } from "./components/StockGraphCard";
import { StockPnLCard } from "./components/StockPnLCard";
import { StockNewsPanel } from "./components/StockNewsPanel";
import { AISummaryCard } from "./components/AISummaryCard";
import { Logo } from "./components/Logo";

function todayIso(): string {
  // Local date, deliberately not toISOString() — that returns UTC, and this app is
  // anchored to SGT (the nightly cron runs 06:00 SGT, writing that day's news and
  // summaries). Before 08:00 SGT, UTC is still on the previous day, so a UTC date
  // would ask the API for yesterday's snapshot every morning. `<input type="date">`
  // also emits local YYYY-MM-DD, so this keeps the initial value and any picked
  // value in the same calendar.
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export default function App() {
  const [selected, setSelected] = useState(PORTFOLIO_OPTION);
  const [date, setDate] = useState(todayIso());
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    getPortfolio(date)
      .then(setPortfolio)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load portfolio"))
      .finally(() => setLoading(false));
  }, [date]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const tickers = portfolio?.holdings.map((h) => h.ticker) ?? [];

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="mb-4">
        <Logo />
      </h1>

      <TopBar
        tickers={tickers}
        selected={selected}
        onSelectedChange={setSelected}
        date={date}
        onDateChange={setDate}
        onModifyClick={() => setModalOpen(true)}
      />

      {loading && <div className="text-sm text-gray-500 dark:text-gray-400">Loading...</div>}
      {error && <div className="text-sm text-red-600 dark:text-red-400">{error}</div>}

      {!loading && !error && portfolio && (
        selected === PORTFOLIO_OPTION ? (
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2 flex flex-col gap-4">
              <PortfolioGraphCard date={date} />
              <AISummaryCard target="portfolio" date={date} />
            </div>
            <div className="flex flex-col gap-4">
              <PortfolioSummaryCard portfolio={portfolio} />
              <ViewStocksNewsPanel holdings={portfolio.holdings} date={date} />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2 flex flex-col gap-4">
              <StockGraphCard ticker={selected} date={date} />
              <AISummaryCard target={selected} date={date} />
            </div>
            <div className="flex flex-col gap-4">
              <StockPnLCard
                ticker={selected}
                holding={portfolio.holdings.find((h) => h.ticker === selected)}
              />
              <StockNewsPanel ticker={selected} date={date} />
            </div>
          </div>
        )
      )}

      {modalOpen && (
        <ModifyPortfolioModal
          holdings={portfolio?.holdings ?? []}
          onClose={() => setModalOpen(false)}
          onChanged={refresh}
        />
      )}
    </div>
  );
}
