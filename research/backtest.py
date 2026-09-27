"""Filters, signals and an event-study backtest for insider purchases.

Point-in-time rule: a trade is only knowable once it's filed, so every signal
enters at the next trading day's OPEN after filing_date, never on trans_date.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

HORIZONS = (21, 63, 126, 252)  # trading days: ~1, 3, 6, 12 months


# --------------------------------------------------------------------------- #
# Data-quality check
# --------------------------------------------------------------------------- #

def add_price_check(purchases: pd.DataFrame, prices: dict[str, pd.DataFrame],
                    tolerance: float = 2.0) -> pd.DataFrame:
    """Compare each reported purchase price with the market close on the trade
    date. Catches unit mix-ups (ADS vs ordinary shares, foreign currency lines)
    that would otherwise produce absurd dollar values. Yahoo prices are
    split-adjusted, so the reported price is divided by the splits that happened
    after the trade before comparing. Dividend adjustment is small enough to
    ignore at this tolerance.

    Adds `price_ratio` and `price_ok` (NaN/None where there's no price data)."""
    out = purchases.copy()
    out["price_ratio"] = np.nan
    for ticker, idx in out.groupby("ticker").groups.items():
        px = prices.get(ticker)
        if px is None:
            continue
        dates = px.index.values
        close = px["Close"].values
        splits = px["Stock Splits"].replace(0, 1).fillna(1).values
        # splits_after[i] = product of split ratios strictly after dates[i]
        splits_after = np.concatenate([np.cumprod(splits[::-1])[::-1][1:], [1.0]])

        rows = out.loc[idx]
        trade_dates = rows["trans_date"].values.astype("datetime64[ns]")
        pos = np.searchsorted(dates, trade_dates, side="right") - 1
        # NaT would sort after every date and silently match the last close
        valid = (pos >= 0) & ~np.isnat(trade_dates)
        p = np.clip(pos, 0, None)
        adj_reported = rows["price"].values / splits_after[p]
        ratio = np.where(valid, adj_reported / close[p], np.nan)
        out.loc[idx, "price_ratio"] = ratio

    r = out["price_ratio"]
    out["price_ok"] = np.where(r.isna(), None, (r >= 1 / tolerance) & (r <= tolerance))
    return out


def add_market_cap(purchases: pd.DataFrame, shares: pd.DataFrame, max_age_days: int = 400) -> pd.DataFrame:
    """market_cap = latest reported shares outstanding on or before the trade
    date x the insider's reported price. Both are as-of the same time and
    unadjusted, so later splits don't distort it (unlike Yahoo's adjusted prices).

    Share counts older than max_age_days are ignored. For companies with several
    share classes the cover page may list only one, so these can be understated.
    Adds `market_cap` (NaN when unknown)."""
    out = purchases.copy()
    out["_cik"] = pd.to_numeric(out["issuer_cik"], errors="coerce")
    out["_date"] = out["trans_date"].fillna(out["filing_date"]).astype("datetime64[ns]")
    out["_row"] = range(len(out))
    known = out.dropna(subset=["_cik"]).astype({"_cik": "int64"}).sort_values("_date")
    sh = (shares.rename(columns={"cik": "_cik", "shares": "_shares_out"})   # "shares" = shares bought
          .astype({"_cik": "int64", "as_of": "datetime64[ns]"})[["_cik", "as_of", "_shares_out"]])
    merged = pd.merge_asof(known, sh.sort_values("as_of"), left_on="_date", right_on="as_of",
                           by="_cik", direction="backward",
                           tolerance=pd.Timedelta(days=max_age_days))
    mcap = (merged["_shares_out"] * merged["price"]).to_numpy()
    out["market_cap"] = np.nan
    out.iloc[merged["_row"].to_numpy(), out.columns.get_loc("market_cap")] = mcap
    return out.drop(columns=["_cik", "_date", "_row"])


# --------------------------------------------------------------------------- #
# Filters -> signals
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Filters:
    officers: bool = True
    directors: bool = True
    ten_pct_owners: bool = False
    ceo_cfo_only: bool = False
    exclude_entities: bool = True        # funds/companies holding board seats
    exclude_10b5_1: bool = True          # pre-planned trades (flag only exists from 2023)
    require_price_ok: bool = True        # drop rows that fail add_price_check
    min_usd: float = 0                   # per filing (all trades in it summed)
    max_usd: float = 5e8                 # sanity cap: bigger is almost always a data error
    min_stake_increase: float | None = None   # e.g. 0.2 = holding grew >= 20%
    max_filing_lag_days: int | None = None    # drop very late filings
    min_market_cap: float | None = None  # e.g. 10e9 = large caps only (needs add_market_cap)
    max_market_cap: float | None = None  # rows with unknown market cap are dropped when either is set
    min_cluster: int = 1                 # distinct insiders buying the ticker...
    cluster_window_days: int = 30        # ...within this many days up to the filing


def apply_filters(purchases: pd.DataFrame, f: Filters) -> pd.DataFrame:
    """Row-level filters. Returns purchases that qualify, with `n_insiders_window`."""
    p = purchases
    role = (
        (f.officers & p["is_officer"])
        | (f.directors & p["is_director"])
        | (f.ten_pct_owners & p["is_ten_pct_owner"])
    )
    keep = role & p["ticker"].notna()
    if f.ceo_cfo_only:
        keep &= p["is_ceo_cfo"]
    if f.exclude_entities:
        keep &= ~p["is_entity"]
    if f.exclude_10b5_1:
        keep &= ~p["is_10b5_1"]
    if f.require_price_ok and "price_ok" in p:
        # Only drop rows that FAILED the check. Rows without price data stay in so
        # run_backtest can count them as "no price" instead of hiding the gap.
        keep &= ~p["price_ok"].eq(False)
    if f.min_market_cap is not None:
        keep &= p["market_cap"] >= f.min_market_cap
    if f.max_market_cap is not None:
        keep &= p["market_cap"] < f.max_market_cap
    if f.max_filing_lag_days is not None:
        keep &= (p["filing_date"] - p["trans_date"]).dt.days <= f.max_filing_lag_days
    p = p[keep].copy()

    # Size filters apply to the whole filing (several small fills = one decision).
    filing_usd = p.groupby("accession")["value_usd"].transform("sum")
    p = p[(filing_usd >= f.min_usd) & (filing_usd <= f.max_usd)]
    if f.min_stake_increase is not None:
        p = p[p["stake_increase"].isna() | (p["stake_increase"] >= f.min_stake_increase)]

    p = _add_cluster_counts(p, f.cluster_window_days)
    return p[p["n_insiders_window"] >= f.min_cluster]


def _add_cluster_counts(p: pd.DataFrame, window_days: int) -> pd.DataFrame:
    """Distinct buyers of the same ticker filed within [filing_date - window, filing_date].
    Only looks backward, so it uses nothing that wasn't public at filing time."""
    p = p.sort_values(["ticker", "filing_date"]).copy()
    counts = np.ones(len(p), dtype=int)
    window = np.timedelta64(window_days, "D")
    offset = 0
    for _, g in p.groupby("ticker", sort=False):
        dates = g["filing_date"].values
        buyers = g["owner_ciks"].values
        lo = np.searchsorted(dates, dates - window, side="left")
        hi = np.searchsorted(dates, dates, side="right")
        counts[offset : offset + len(g)] = [len(set(buyers[a:b])) for a, b in zip(lo, hi)]
        offset += len(g)
    p["n_insiders_window"] = counts
    return p


def build_signals(filtered: pd.DataFrame, cooldown_days: int = 30) -> pd.DataFrame:
    """One signal per ticker per filing date. After a signal, further signals
    for the same ticker within `cooldown_days` are dropped so one buying spree
    isn't counted as many independent bets."""
    sig = (
        filtered.groupby(["ticker", "filing_date"])
        .agg(
            issuer_name=("issuer_name", "first"),
            value_usd=("value_usd", "sum"),
            n_filings=("accession", "nunique"),
            n_insiders_window=("n_insiders_window", "max"),
            owners=("owner_names", lambda s: "; ".join(sorted(set(s)))),
        )
        .reset_index()
        .sort_values(["ticker", "filing_date"])
    )
    if cooldown_days:
        keep, last = [], {}
        for t, d in zip(sig["ticker"], sig["filing_date"]):
            ok = t not in last or (d - last[t]).days > cooldown_days
            keep.append(ok)
            if ok:
                last[t] = d
        sig = sig[keep]
    return sig.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Backtest
# --------------------------------------------------------------------------- #

MAX_DAILY_RETURN = 3.0  # a +300% day inside a hold is treated as a price-data error


def _suspect(close: np.ndarray, i: int, j: int, max_daily_return: float) -> bool:
    """True if the close-to-close moves over [i, j) include an implausible jump.
    Yahoo occasionally misses a reverse split or has a bad tick (e.g. +6,800% in
    a day), which would otherwise dominate averages."""
    seg = close[max(i - 1, 0):j]
    return len(seg) > 1 and bool(np.nanmax(seg[1:] / seg[:-1]) - 1 > max_daily_return)


@dataclass
class BacktestResult:
    events: pd.DataFrame
    horizons: tuple[int, ...]
    n_signals: int
    n_no_price: int = field(default=0)
    n_bad_data: int = field(default=0)

    def coverage(self) -> str:
        pct = 100 * self.n_no_price / max(self.n_signals, 1)
        return (f"{self.n_signals} signals, {self.n_no_price} ({pct:.0f}%) had no price data "
                f"-> those are missing from the results (survivorship bias risk); "
                f"{self.n_bad_data} dropped for suspect price data (>{MAX_DAILY_RETURN:.0%} in a day)")

    def summary(self) -> pd.DataFrame:
        rows = []
        for h in self.horizons:
            ex = self.events[f"excess_{h}"].dropna()
            ret = self.events[f"ret_{h}"].dropna()
            rows.append({
                "hold_days": h,
                "n": len(ex),
                "mean_ret": ret.mean(),
                "mean_excess": ex.mean(),
                "median_excess": ex.median(),
                "hit_rate": (ex > 0).mean(),
                # naive: overlapping holds make this overstate significance
                "t_stat": ex.mean() / (ex.std(ddof=1) / np.sqrt(len(ex))) if len(ex) > 1 else np.nan,
                "delisted_exits": int(self.events[f"truncated_{h}"].sum()),
            })
        return pd.DataFrame(rows).set_index("hold_days")

    def by_year(self, hold_days: int) -> pd.DataFrame:
        e = self.events.dropna(subset=[f"excess_{hold_days}"])
        return (
            e.groupby(e["entry_date"].dt.year)[f"excess_{hold_days}"]
            .agg(n="count", mean_excess="mean", median_excess="median")
        )


def run_backtest(signals: pd.DataFrame, prices: dict[str, pd.DataFrame], benchmark: str = "SPY",
                 horizons=HORIZONS, cost_bps: float = 50,
                 max_daily_return: float = MAX_DAILY_RETURN) -> BacktestResult:
    """Event study: buy at the next open after filing_date, hold N trading days,
    exit at the close. Excess return = stock return (minus round-trip cost)
    minus the benchmark's return over the same dates.

    If a stock's price history ends before the hold is over (likely delisted),
    the last available close is used instead of dropping the trade, since
    dropping failures would flatter the results."""
    bench = prices[benchmark]
    b_dates, b_open, b_close = bench.index.values, bench["Open"].values, bench["Close"].values
    data_end = max(df.index.max() for df in prices.values())
    cost = cost_bps / 10_000

    rows, no_price, bad_data = [], 0, 0
    for s in signals.itertuples(index=False):
        px = prices.get(s.ticker)
        if px is None:
            no_price += 1
            continue
        dates = px.index.values
        i = np.searchsorted(dates, np.datetime64(s.filing_date), side="right")
        if i >= len(dates):
            continue  # filed after our price data ends
        entry_price = px["Open"].iat[i]
        if not entry_price > 0:
            continue
        if _suspect(px["Close"].values, i, i + max(horizons), max_daily_return):
            bad_data += 1
            continue
        # A series that stops well before the data end means the stock stopped trading.
        delisted = (data_end - px.index[-1]).days > 7

        row = {"ticker": s.ticker, "issuer_name": s.issuer_name, "filing_date": s.filing_date,
               "entry_date": px.index[i], "value_usd": s.value_usd,
               "n_insiders_window": s.n_insiders_window, "owners": s.owners}
        for h in horizons:
            j = i + h - 1
            truncated = False
            if j >= len(dates):
                if not delisted:
                    row.update({f"ret_{h}": np.nan, f"excess_{h}": np.nan, f"truncated_{h}": False})
                    continue  # hold not finished yet
                j, truncated = len(dates) - 1, True
            ret = px["Close"].iat[j] / entry_price - 1 - cost

            bi = np.searchsorted(b_dates, dates[i], side="left")
            bj = np.searchsorted(b_dates, dates[j], side="right") - 1
            bench_ret = b_close[bj] / b_open[bi] - 1 if bi < len(b_dates) and bj >= bi else np.nan
            row.update({f"ret_{h}": ret, f"excess_{h}": ret - bench_ret, f"truncated_{h}": truncated})
        rows.append(row)

    return BacktestResult(pd.DataFrame(rows), tuple(horizons), len(signals), no_price, bad_data)


def compare(variants: dict[str, Filters], purchases: pd.DataFrame, prices: dict[str, pd.DataFrame],
            hold_days: int = 126, **backtest_kwargs) -> pd.DataFrame:
    """Run several filter variants and line up their results at one horizon."""
    out = []
    for name, f in variants.items():
        res = run_backtest(build_signals(apply_filters(purchases, f)), prices, **backtest_kwargs)
        s = res.summary().loc[hold_days].to_dict()
        s["n"], s["delisted_exits"] = int(s["n"]), int(s["delisted_exits"])
        out.append({"variant": name, "signals": res.n_signals, "no_price": res.n_no_price,
                    "bad_data": res.n_bad_data, **s})
    return pd.DataFrame(out).set_index("variant")


# --------------------------------------------------------------------------- #
# Portfolio simulation -> Sharpe
# --------------------------------------------------------------------------- #

def portfolio_returns(signals: pd.DataFrame, prices: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex,
                      hold_days: int = 63, cost_bps: float = 50, rf_daily: pd.Series | None = None,
                      max_daily_return: float = MAX_DAILY_RETURN) -> pd.DataFrame:
    """Daily returns of a portfolio that puts the same amount into every signal
    at the next open after filing_date and holds it `hold_days` trading days.
    Positions then drift with their own price (buy-and-hold weights), like a real
    account; daily re-equalising would turn a spike that reverses into a fake
    profit. Round-trip cost is charged on the entry day. Days with no open
    position earn the risk-free rate (or 0). Signals with suspect price data are
    skipped, as in run_backtest. Returns DataFrame[ret, n_positions] on `calendar`."""
    cost = cost_bps / 10_000
    dates_all, rets_all, weights_all = [], [], []
    for s in signals.itertuples(index=False):
        px = prices.get(s.ticker)
        if px is None:
            continue
        dates = px.index.values
        i = np.searchsorted(dates, np.datetime64(s.filing_date), side="right")
        if i >= len(dates) or not px["Open"].iat[i] > 0:
            continue
        j = min(i + hold_days, len(dates))  # stops early if the stock stopped trading
        close = px["Close"].values
        if _suspect(close, i, j, max_daily_return):
            continue
        r = np.empty(j - i)
        r[0] = close[i] / px["Open"].iat[i] - 1 - cost      # entry day: open -> close
        r[1:] = close[i + 1:j] / close[i:j - 1] - 1         # then close -> close
        # value of the position at the start of each day, per $1 invested
        w = np.concatenate([[1.0], np.cumprod(1 + r)[:-1]])
        dates_all.append(dates[i:j])
        rets_all.append(r)
        weights_all.append(w)

    if rets_all:
        daily = pd.DataFrame({"date": np.concatenate(dates_all), "r": np.concatenate(rets_all),
                              "w": np.concatenate(weights_all)})
        daily = daily[np.isfinite(daily["r"]) & np.isfinite(daily["w"])]
        daily["wr"] = daily["w"] * daily["r"]
        g = daily.groupby("date")
        daily = pd.DataFrame({"mean": g["wr"].sum() / g["w"].sum(), "size": g.size()})
    else:
        daily = pd.DataFrame(columns=["mean", "size"], dtype=float)
    out = pd.DataFrame(index=calendar)
    out["n_positions"] = daily["size"].reindex(calendar).fillna(0).astype(int)
    cash = rf_daily.reindex(calendar).ffill().fillna(0) if rf_daily is not None else 0.0
    out["ret"] = daily["mean"].reindex(calendar).where(out["n_positions"] > 0, cash)
    return out


def performance(ret: pd.Series, bench: pd.Series, rf_daily: pd.Series | None = None) -> dict:
    """Annualised stats for a daily return series vs a benchmark on the same dates."""
    rf = rf_daily.reindex(ret.index).ffill().fillna(0) if rf_daily is not None else 0.0
    ex = ret - rf
    active = ret - bench
    wealth = (1 + ret).cumprod()
    years = len(ret) / 252
    return {
        "ann_return": wealth.iloc[-1] ** (1 / years) - 1,
        "ann_vol": ret.std() * np.sqrt(252),
        "sharpe": ex.mean() / ex.std() * np.sqrt(252),
        "max_drawdown": (wealth / wealth.cummax() - 1).min(),
        "beta": np.cov(ret, bench)[0, 1] / bench.var(),
        "info_ratio": active.mean() / active.std() * np.sqrt(252) if active.std() > 0 else np.nan,
    }


def compare_sharpe(variants: dict[str, Filters], purchases: pd.DataFrame, prices: dict[str, pd.DataFrame],
                   benchmark: str = "SPY", hold_days: int = 63, cost_bps: float = 50,
                   rf_daily: pd.Series | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sharpe etc. for each variant's portfolio and for the benchmark, all over
    the same trading days (first possible entry -> end of price data).
    Returns (stats table, daily returns per variant incl. benchmark)."""
    b = prices[benchmark]
    start = purchases["filing_date"].min()
    calendar = b.index[b.index > start]
    bench_ret = b["Close"].pct_change().reindex(calendar)
    bench_ret.iloc[0] = b["Close"].loc[calendar[0]] / b["Open"].loc[calendar[0]] - 1

    rows, series = [], {benchmark: bench_ret}
    for name, f in variants.items():
        pr = portfolio_returns(build_signals(apply_filters(purchases, f)), prices, calendar,
                               hold_days, cost_bps, rf_daily)
        series[name] = pr["ret"]
        rows.append({"variant": name, **performance(pr["ret"], bench_ret, rf_daily),
                     "avg_positions": pr["n_positions"].mean(),
                     "days_in_cash": (pr["n_positions"] == 0).mean()})
    rows.append({"variant": f"{benchmark} (buy & hold)", **performance(bench_ret, bench_ret, rf_daily),
                 "avg_positions": np.nan, "days_in_cash": 0.0})
    return pd.DataFrame(rows).set_index("variant"), pd.DataFrame(series)


__all__ = ["Filters", "replace", "add_price_check", "add_market_cap", "apply_filters", "build_signals",
           "run_backtest", "compare", "BacktestResult", "HORIZONS",
           "portfolio_returns", "performance", "compare_sharpe"]
