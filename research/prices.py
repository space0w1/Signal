"""Daily prices via yfinance, cached one Parquet file per ticker.

Caveat: Yahoo mostly drops delisted tickers, so companies that later went bust
or were acquired tend to be missing. That biases a backtest upward (survivorship
bias). Always look at how many signals had no price data before trusting results.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

MISSING_FILE = "_missing.txt"
META_FILE = "_meta.json"

# yfinance logs a line per unknown ticker; the summary printed by fetch_prices is enough.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def yahoo_symbol(ticker: str) -> str:
    # SEC filings write class shares as BRK.B; Yahoo uses BRK-B
    return ticker.replace(".", "-").replace("/", "-")


def _cache_path(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / f"{yahoo_symbol(ticker)}.parquet"


def fetch_prices(tickers, start: str, cache_dir: Path, batch_size: int = 100, refresh: bool = False) -> None:
    """Download adjusted daily Open/Close plus split events for any ticker not
    yet cached. Tickers Yahoo doesn't know are remembered in _missing.txt so
    reruns don't retry them. refresh=True re-downloads everything (e.g. to
    extend cached series up to today)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Cached series only go back as far as the start they were fetched with.
    meta_path = cache_dir / META_FILE
    if meta_path.exists() and json.loads(meta_path.read_text())["start"] > start:
        print(f"cache starts later than {start}; re-downloading everything")
        refresh = True
    if refresh or not meta_path.exists():
        meta_path.write_text(json.dumps({"start": start}))
    missing_path = cache_dir / MISSING_FILE
    if refresh:
        missing_path.unlink(missing_ok=True)
    known_missing = set(missing_path.read_text().split()) if missing_path.exists() else set()

    todo = sorted(
        {t for t in tickers if t}
        - known_missing
        - (set() if refresh else {t for t in tickers if t and _cache_path(cache_dir, t).exists()})
    )
    print(f"{len(todo)} tickers to download")

    newly_missing = []
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        symbols = [yahoo_symbol(t) for t in batch]
        raw = yf.download(
            symbols, start=start, auto_adjust=True, actions=True,
            group_by="ticker", threads=True, progress=False,
        )
        for ticker, sym in zip(batch, symbols):
            try:
                df = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
                df = df[["Open", "Close", "Stock Splits"]].dropna(subset=["Open", "Close"])
            except KeyError:
                df = pd.DataFrame()
            if df.empty:
                newly_missing.append(ticker)
                continue
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.to_parquet(_cache_path(cache_dir, ticker))
        done = min(i + batch_size, len(todo))
        if done % (batch_size * 10) == 0 or done == len(todo):
            print(f"  {done}/{len(todo)}")

    if newly_missing:
        with missing_path.open("a") as f:
            f.write("\n".join(newly_missing) + "\n")
    print(f"done; {len(newly_missing)} tickers had no data on Yahoo")


def load_prices(tickers, cache_dir: Path) -> dict[str, pd.DataFrame]:
    """{ticker: DataFrame[Open, Close, Stock Splits]} for every cached ticker."""
    out = {}
    for t in {t for t in tickers if t}:
        p = _cache_path(cache_dir, t)
        if p.exists():
            out[t] = pd.read_parquet(p)
    return out
