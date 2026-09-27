import { useEffect, useMemo, useState } from "react";
import { getWorldMarkets, type WorldMarket, type WorldPeriod } from "../api/client";
import { WorldGlobe } from "../components/WorldGlobe";
import type { Theme } from "../theme";
import { formatPercent, pnlColorClass } from "../utils/format";
import { COLOR_SCALE, changeColor } from "../utils/worldColors";

const PERIODS: { value: WorldPeriod; label: string }[] = [
  { value: "change_1d", label: "1D" },
  { value: "change_1w", label: "1W" },
  { value: "change_1m", label: "1M" },
  { value: "change_ytd", label: "YTD" },
];

function formatClose(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("en-SG", { maximumFractionDigits: 2 });
}

function Legend({ period, dark }: { period: WorldPeriod; dark: boolean }) {
  const scale = COLOR_SCALE[period];
  const stops = [-1, -0.5, 0, 0.5, 1].map((t) => changeColor(t * scale, period, dark)).join(", ");
  return (
    <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
      <span>{formatPercent(-scale)}</span>
      <div className="h-2 w-40 rounded-full" style={{ background: `linear-gradient(to right, ${stops})` }} />
      <span>{formatPercent(scale)}</span>
      <span className="ml-2 flex items-center gap-1">
        <span className="inline-block h-2 w-3 rounded-sm" style={{ background: changeColor(null, period, dark) }} />
        no data / not tracked
      </span>
    </div>
  );
}

function MarketDetail({ market }: { market: WorldMarket }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
      <div className="text-sm font-medium text-gray-700 dark:text-gray-300">{market.country}</div>
      <div className="mt-1 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span>
          {market.index_name} · {market.symbol}
        </span>
        {market.kind === "etf" && (
          <span
            className="rounded bg-gray-100 px-1.5 py-0.5 dark:bg-gray-800"
            title="No index history available, so a US-listed country ETF stands in for this market"
          >
            ETF proxy
          </span>
        )}
        {market.stale && <span className="text-amber-600 dark:text-amber-400">stale</span>}
      </div>
      <div className="mt-3 text-2xl font-semibold text-gray-900 dark:text-gray-100">
        {formatClose(market.last_close)} <span className="text-sm font-normal text-gray-500">{market.currency}</span>
      </div>
      <div className="text-xs text-gray-400 dark:text-gray-500">as of {market.as_of ?? "—"}</div>
      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
        {PERIODS.map((p) => {
          const change = market[p.value];
          return (
            <div key={p.value} className="rounded-lg bg-gray-100 py-1.5 dark:bg-gray-800">
              <div className="text-xs text-gray-500 dark:text-gray-400">{p.label}</div>
              <div className={`text-sm font-medium ${change === null ? "text-gray-400" : pnlColorClass(change)}`}>
                {change === null ? "—" : formatPercent(change)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function WorldPage({ theme }: { theme: Theme }) {
  const [markets, setMarkets] = useState<WorldMarket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<WorldPeriod>("change_1d");
  const [selectedIso, setSelectedIso] = useState<string | null>(null);

  useEffect(() => {
    getWorldMarkets()
      .then(setMarkets)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load world markets"))
      .finally(() => setLoading(false));
  }, []);

  const ranked = useMemo(
    () => [...markets].sort((a, b) => (b[period] ?? -Infinity) - (a[period] ?? -Infinity)),
    [markets, period],
  );
  const selected = markets.find((m) => m.iso_n3 === selectedIso);
  const latestDate = markets.reduce<string | null>((d, m) => (m.as_of && (!d || m.as_of > d) ? m.as_of : d), null);

  return (
    <>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">World markets</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Each country's headline stock index, in its own currency
            {latestDate && (
              <>
                {" · latest close "}
                <span className="font-semibold text-gray-700 dark:text-gray-300">{latestDate}</span>
              </>
            )}
          </p>
        </div>
        <div className="flex rounded-lg bg-gray-100 p-1 text-xs font-medium dark:bg-gray-800">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`rounded-md px-3 py-1 ${
                period === p.value ? "bg-white shadow-sm dark:bg-gray-700 dark:text-gray-100" : "text-gray-500 dark:text-gray-400"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="text-sm text-gray-500 dark:text-gray-400">Loading...</div>}
      {error && <div className="text-sm text-red-600 dark:text-red-400">{error}</div>}

      {!loading && !error && (
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
            <WorldGlobe
              markets={markets}
              period={period}
              theme={theme}
              selectedIso={selectedIso}
              onSelect={setSelectedIso}
            />
            <Legend period={period} dark={theme === "dark"} />
          </div>

          <div className="flex flex-col gap-4">
            {selected ? (
              <MarketDetail market={selected} />
            ) : (
              <div className="rounded-xl border border-dashed border-gray-200 p-4 text-sm text-gray-400 dark:border-gray-700 dark:text-gray-500">
                Click a country on the globe or in the list for details.
              </div>
            )}

            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
              <div className="border-b border-gray-100 px-4 py-2 text-sm font-medium text-gray-700 dark:border-gray-800 dark:text-gray-300">
                Ranked by {PERIODS.find((p) => p.value === period)?.label} change
              </div>
              <ul className="max-h-[360px] overflow-y-auto">
                {ranked.map((m) => {
                  const change = m[period];
                  return (
                    <li key={m.iso_n3}>
                      <button
                        onClick={() => setSelectedIso(m.iso_n3)}
                        className={`flex w-full items-center justify-between px-4 py-1.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800 ${
                          m.iso_n3 === selectedIso ? "bg-gray-100 dark:bg-gray-800" : ""
                        }`}
                      >
                        <span className="text-gray-700 dark:text-gray-300">
                          {m.country}
                          <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">{m.index_name}</span>
                        </span>
                        <span className={`font-medium ${change === null ? "text-gray-400" : pnlColorClass(change)}`}>
                          {change === null ? "—" : formatPercent(change)}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
