export type Region = "US" | "HK" | "SG";

export interface HoldingPnL {
  ticker: string;
  exchange: string;
  currency: string;
  quantity: number;
  price: number;
  price_date: string;
  avg_cost: number;
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

export type GraphMode = "aggregate" | "overlay";

export interface AggregatePoint {
  date: string;
  total_value_sgd: number;
  total_cost_sgd: number;
  total_unrealized_pnl_amount: number;
  total_realized_pnl_sgd: number;
}

export interface OverlayPoint {
  date: string;
  pnl_pct: number;
}

export interface PortfolioGraph {
  mode: GraphMode;
  aggregate: AggregatePoint[] | null;
  overlay: Record<string, OverlayPoint[]> | null;
  overlay_portfolio: OverlayPoint[] | null;
}

export interface StockGraphPoint {
  date: string;
  price: number;
  currency: string;
  pnl_pct: number | null;
  pnl_amount_sgd: number | null;
}

export interface NewsItem {
  id: number;
  ticker: string;
  headline: string;
  source: string | null;
  url: string | null;
  thumbnail_url: string | null;
  published_at: string | null;
  fetched_date: string;
}

export interface Summary {
  target_type: string;
  ticker: string | null;
  date: string;
  summary: string;
  next_steps: string;
  cited_news: NewsItem[];
  generated_at: string;
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

export function getPortfolioGraph(date: string, mode: GraphMode): Promise<PortfolioGraph> {
  return request<PortfolioGraph>(`/graph/portfolio?date=${date}&mode=${mode}`);
}

export function getStockGraph(ticker: string, date: string): Promise<StockGraphPoint[]> {
  return request<StockGraphPoint[]>(`/graph/stock/${encodeURIComponent(ticker)}?date=${date}`);
}

export function getNewsForStock(ticker: string, date: string): Promise<NewsItem[]> {
  return request<NewsItem[]>(`/news/stock/${encodeURIComponent(ticker)}?date=${date}`);
}

export function getSummary(target: string, date: string): Promise<Summary> {
  return request<Summary>(`/summary?target=${encodeURIComponent(target)}&date=${date}`);
}

export function addHolding(payload: {
  symbol: string;
  region: Region;
  qty: number;
  cost: number;
  date?: string;
}): Promise<Holding> {
  return request<Holding>("/holdings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function sellHolding(
  ticker: string,
  payload: { qty: number; price: number; date?: string },
): Promise<SellResult> {
  return request<SellResult>(`/holdings/${encodeURIComponent(ticker)}/sell`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
