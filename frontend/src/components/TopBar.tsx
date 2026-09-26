import { useTheme } from "../theme";

export const PORTFOLIO_OPTION = "PORTFOLIO";

interface TopBarProps {
  tickers: string[];
  selected: string;
  onSelectedChange: (value: string) => void;
  date: string;
  onDateChange: (value: string) => void;
  onModifyClick: () => void;
}

export function TopBar({
  tickers,
  selected,
  onSelectedChange,
  date,
  onDateChange,
  onModifyClick,
}: TopBarProps) {
  const [theme, toggleTheme] = useTheme();

  return (
    <div className="mb-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <select
          value={selected}
          onChange={(e) => onSelectedChange(e.target.value)}
          className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm font-medium shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value={PORTFOLIO_OPTION}>Portfolio</option>
          {tickers.map((ticker) => (
            <option key={ticker} value={ticker}>
              {ticker}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={date}
          onChange={(e) => onDateChange(e.target.value)}
          className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800"
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
        <button
          onClick={onModifyClick}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
        >
          Modify Portfolio
        </button>
      </div>
    </div>
  );
}
