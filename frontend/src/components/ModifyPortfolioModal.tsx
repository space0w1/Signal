import { useState } from "react";
import { addHolding, sellHolding, type HoldingPnL, type Region } from "../api/client";

interface Props {
  holdings: HoldingPnL[];
  onClose: () => void;
  onChanged: () => void;
}

export function ModifyPortfolioModal({ holdings, onClose, onChanged }: Props) {
  const [symbol, setSymbol] = useState("");
  const [region, setRegion] = useState<Region>("US");
  const [qty, setQty] = useState("");
  const [cost, setCost] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [addLoading, setAddLoading] = useState(false);

  const [sellTicker, setSellTicker] = useState<string | null>(null);
  const [sellQty, setSellQty] = useState("");
  const [sellPrice, setSellPrice] = useState("");
  const [sellError, setSellError] = useState<string | null>(null);
  const [sellLoading, setSellLoading] = useState(false);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAddError(null);
    setAddLoading(true);
    try {
      await addHolding({ symbol: symbol.trim(), region, qty: Number(qty), cost: Number(cost) });
      setSymbol("");
      setQty("");
      setCost("");
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
      await sellHolding(ticker, { qty: Number(sellQty), price: Number(sellPrice) });
      setSellTicker(null);
      setSellQty("");
      setSellPrice("");
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
            <input
              placeholder="Symbol"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              required
              className="rounded-md border border-gray-200 px-2 py-1.5 text-sm"
            />
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value as Region)}
              className="rounded-md border border-gray-200 px-2 py-1.5 text-sm"
            >
              <option value="US">US</option>
              <option value="HK">HK</option>
              <option value="SG">SG</option>
            </select>
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
          </div>
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
                    </div>
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
