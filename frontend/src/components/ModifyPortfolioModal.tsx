import { useEffect, useRef, useState } from "react";
import {
  addHolding,
  searchSymbols,
  sellHolding,
  type HoldingPnL,
  type SymbolMatch,
} from "../api/client";

interface Props {
  holdings: HoldingPnL[];
  onClose: () => void;
  onChanged: () => void;
}

export function ModifyPortfolioModal({ holdings, onClose, onChanged }: Props) {
  const [symbol, setSymbol] = useState("");
  // Display only — the backend resolves the region itself. Shown so a picked
  // suggestion confirms which market it came from.
  const [pickedRegion, setPickedRegion] = useState<string | null>(null);
  const [matches, setMatches] = useState<SymbolMatch[]>([]);
  const [searching, setSearching] = useState(false);
  const [showMatches, setShowMatches] = useState(false);
  // Set when a suggestion is picked, so the effect below doesn't immediately re-search
  // for the exact symbol it just filled in and reopen the dropdown.
  const justPicked = useRef(false);

  const [qty, setQty] = useState("");
  const [cost, setCost] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [addLoading, setAddLoading] = useState(false);

  const [sellTicker, setSellTicker] = useState<string | null>(null);
  const [sellQty, setSellQty] = useState("");
  const [sellPrice, setSellPrice] = useState("");
  const [sellDate, setSellDate] = useState("");
  const [sellError, setSellError] = useState<string | null>(null);
  const [sellLoading, setSellLoading] = useState(false);

  // Debounced symbol lookup. 250ms is short enough to feel live while collapsing a
  // burst of keystrokes into one upstream Yahoo call, and the AbortController drops
  // the response of any request a newer keystroke has superseded — otherwise a slow
  // early request can land last and overwrite the results for what was actually typed.
  useEffect(() => {
    if (justPicked.current) {
      justPicked.current = false;
      return;
    }
    const q = symbol.trim();
    if (q.length < 2) {
      setMatches([]);
      setSearching(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setSearching(true);
      searchSymbols(q, controller.signal)
        .then((rs) => {
          setMatches(rs);
          setShowMatches(true);
        })
        .catch(() => {
          // Includes the abort of a superseded request — leave the current list alone
          // rather than flashing "no matches" while a newer search is still in flight.
        })
        .finally(() => setSearching(false));
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [symbol]);

  function pickMatch(m: SymbolMatch) {
    justPicked.current = true;
    setSymbol(m.symbol);
    setPickedRegion(m.region); // display only; the backend resolves it again authoritatively
    setShowMatches(false);
    setMatches([]);
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAddError(null);
    setAddLoading(true);
    try {
      await addHolding({
        symbol: symbol.trim(),
        qty: Number(qty),
        cost: Number(cost),
        date: purchaseDate || undefined,
      });
      setSymbol("");
      setPickedRegion(null);
      setMatches([]);
      setShowMatches(false);
      setQty("");
      setCost("");
      setPurchaseDate("");
      onChanged();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add holding");
    } finally {
      setAddLoading(false);
    }
  }

  async function handleSell(ticker: string) {
    setSellError(null);
    setSellLoading(true);
    try {
      await sellHolding(ticker, {
        qty: Number(sellQty),
        price: Number(sellPrice),
        date: sellDate || undefined,
      });
      setSellTicker(null);
      setSellQty("");
      setSellPrice("");
      setSellDate("");
      onChanged();
    } catch (err) {
      setSellError(err instanceof Error ? err.message : "Failed to sell holding");
    } finally {
      setSellLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Modify Portfolio</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            ✕
          </button>
        </div>

        <form onSubmit={handleAdd} className="mb-5 space-y-2 rounded-lg border border-gray-200 p-3">
          <div className="text-sm font-medium text-gray-700">Add Holding</div>
          <div className="grid grid-cols-2 gap-2">
            {/* relative wrapper so the suggestion list can overlay the fields below
                instead of pushing the rest of the form down as you type */}
            <div className="relative">
              <input
                placeholder="Symbol or company"
                value={symbol}
                onChange={(e) => {
                  setSymbol(e.target.value);
                  setPickedRegion(null);
                }}
                onFocus={() => matches.length > 0 && setShowMatches(true)}
                // Escape dismisses the list without clearing what's typed. Blur is
                // delayed because mousedown on a suggestion fires blur first, which
                // would unmount the list before the click could register.
                onKeyDown={(e) => e.key === "Escape" && setShowMatches(false)}
                onBlur={() => setTimeout(() => setShowMatches(false), 120)}
                autoComplete="off"
                required
                className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-sm"
              />
              {searching && (
                <span className="absolute right-2 top-1.5 text-xs text-gray-400">…</span>
              )}
              {showMatches && matches.length > 0 && (
                <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-gray-200 bg-white shadow-lg">
                  {matches.map((m) => (
                    <li key={`${m.symbol}-${m.exchange}`}>
                      <button
                        type="button"
                        onClick={() => pickMatch(m)}
                        className="flex w-full items-baseline justify-between gap-2 px-2 py-1.5 text-left text-xs hover:bg-blue-50"
                      >
                        <span className="font-medium text-gray-800">{m.symbol}</span>
                        <span className="min-w-0 flex-1 truncate text-gray-500">{m.name}</span>
                        <span className="shrink-0 rounded bg-gray-100 px-1 text-gray-600">
                          {m.region}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {showMatches && !searching && symbol.trim().length >= 2 && matches.length === 0 && (
                <div className="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-500 shadow-lg">
                  No US/HK/SG match — you can still type an exact ticker.
                </div>
              )}
            </div>
            <div className="flex items-center rounded-md border border-dashed border-gray-200 px-2 py-1.5 text-sm text-gray-500">
              {pickedRegion ? (
                <span className="font-medium text-gray-700">{pickedRegion}</span>
              ) : (
                <span className="text-xs">Market: auto</span>
              )}
            </div>
            <input
              placeholder="Qty"
              type="number"
              step="any"
              min="0"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              required
              className="rounded-md border border-gray-200 px-2 py-1.5 text-sm"
            />
            <input
              placeholder="Cost / share"
              type="number"
              step="any"
              min="0"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              required
              className="rounded-md border border-gray-200 px-2 py-1.5 text-sm"
            />
            <input
              type="date"
              value={purchaseDate}
              onChange={(e) => setPurchaseDate(e.target.value)}
              title="Purchase date (defaults to today)"
              className="col-span-2 rounded-md border border-gray-200 px-2 py-1.5 text-sm text-gray-600"
            />
          </div>
          <div className="text-xs text-gray-400">Purchase date defaults to today if left blank.</div>
          {addError && <div className="text-xs text-red-600">{addError}</div>}
          <button
            type="submit"
            disabled={addLoading}
            className="w-full rounded-md bg-blue-600 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {addLoading ? "Adding..." : "Add"}
          </button>
        </form>

        <div className="mb-2 text-sm font-medium text-gray-700">Current Holdings</div>
        {holdings.length === 0 ? (
          <div className="text-sm text-gray-400">No holdings yet.</div>
        ) : (
          <ul className="space-y-2">
            {holdings.map((h) => (
              <li key={h.ticker} className="rounded-lg border border-gray-200 p-3">
                <button
                  className="flex w-full items-center justify-between text-left"
                  onClick={() => {
                    setSellTicker(sellTicker === h.ticker ? null : h.ticker);
                    setSellError(null);
                  }}
                >
                  <div>
                    <div className="font-medium">{h.ticker}</div>
                    <div className="text-xs text-gray-500">{h.quantity} sh held</div>
                  </div>
                  <span className="text-xs text-blue-600">
                    {sellTicker === h.ticker ? "Cancel" : "Sell"}
                  </span>
                </button>
                {sellTicker === h.ticker && (
                  <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        placeholder="Qty to sell"
                        type="number"
                        step="any"
                        min="0"
                        value={sellQty}
                        onChange={(e) => setSellQty(e.target.value)}
                        className="rounded-md border border-gray-200 px-2 py-1.5 text-sm"
                      />
                      <input
                        placeholder="Sale price"
                        type="number"
                        step="any"
                        min="0"
                        value={sellPrice}
                        onChange={(e) => setSellPrice(e.target.value)}
                        className="rounded-md border border-gray-200 px-2 py-1.5 text-sm"
                      />
                      <input
                        type="date"
                        value={sellDate}
                        onChange={(e) => setSellDate(e.target.value)}
                        title="Sale date (defaults to today)"
                        className="col-span-2 rounded-md border border-gray-200 px-2 py-1.5 text-sm text-gray-600"
                      />
                    </div>
                    <div className="text-xs text-gray-400">Sale date defaults to today if left blank.</div>
                    {sellError && <div className="text-xs text-red-600">{sellError}</div>}
                    <button
                      type="button"
                      disabled={sellLoading}
                      onClick={() => handleSell(h.ticker)}
                      className="w-full rounded-md bg-red-600 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      {sellLoading ? "Selling..." : "Confirm Sell"}
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
