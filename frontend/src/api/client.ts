export type Region = "US" | "HK" | "SG";

export interface HoldingPnL {
  ticker: string;
  exchange: string;
  currency: string;
  quantity: number;
  price: number;
  price_date: string;
  value_sgd: number;
  cost_sgd: number;
  unrealized_pnl_amount: number;
  unrealized_pnl_pct: number;
  realized_pnl_sgd: number;
}

export interface Portfolio {
  date: string;
  total_value_sgd: number;
  total_cost_sgd: number;
  total_unrealized_pnl_amount: number;
  total_unrealized_pnl_pct: number;
  total_realized_pnl_sgd: number;
  holdings: HoldingPnL[];
}

export interface Holding {
  id: number;
  ticker: string;
  exchange: string;
  currency: string;
  total_quantity: number;
  total_cost: number;
  realized_pnl: number;
  date_added: string;
  is_active: boolean;
}

export interface SellResult {
  id: number;
  ticker: string;
  exchange: string;
  currency: string;
  total_quantity: number;
  total_cost: number;
  realized_pnl: number;
  is_active: boolean;
  removed_date: string | null;
  sale_realized_pnl: number;
}

class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0]?.msg
          ? detail[0].msg
          : `Request failed (${res.status})`;
    throw new ApiError(message);
  }

  return res.json() as Promise<T>;
}

export function getPortfolio(date?: string): Promise<Portfolio> {
  const query = date ? `?date=${date}` : "";
  return request<Portfolio>(`/portfolio${query}`);
}

export function addHolding(payload: {
  symbol: string;
  region: Region;
  qty: number;
  cost: number;
}): Promise<Holding> {
  return request<Holding>("/holdings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function sellHolding(
  ticker: string,
  payload: { qty: number; price: number },
): Promise<SellResult> {
  return request<SellResult>(`/holdings/${encodeURIComponent(ticker)}/sell`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
