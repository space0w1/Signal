"""Symbol search for the Modify Portfolio flow, backed by yfinance's Yahoo search.

Yahoo returns every listing worldwide plus futures, options and funds, so this narrows
the result to instruments the app can actually value: equities and ETFs on the three
exchanges whose currency it tracks. Crucially the region comes from Yahoo's own
`exchange` code rather than from parsing the ticker suffix — docs/api.md records that a
typo'd `.SG` instead of `.SI` silently produced a wrong-currency holding, which suffix
guessing invites and an authoritative exchange field avoids.
"""

from dataclasses import dataclass

import yfinance as yf

# Yahoo exchange code -> the app's region. Anything absent is dropped: the app values
# holdings in USD/HKD/SGD only, so a Buenos Aires or Vienna listing has no valid region
# to offer. OTC/pink-sheet (PNK) is deliberately excluded too — those listings carry
# thin price history and mostly duplicate a primary listing as an ADR.
EXCHANGE_REGION = {
    "NMS": "US",  # Nasdaq Global Select
    "NAS": "US",  # Nasdaq
    "NGM": "US",  # Nasdaq Global Market
    "NCM": "US",  # Nasdaq Capital Market
    "NYQ": "US",  # NYSE
    "ASE": "US",  # NYSE American
    "PCX": "US",  # NYSE Arca
    "BTS": "US",  # Cboe BZX
    "HKG": "HK",  # Hong Kong
    "SES": "SG",  # Singapore
}

# Instrument kinds with a daily close and a currency. Futures, options, money-market
# and mutual funds are excluded — the portfolio model has no way to value them.
TRADABLE_TYPES = {"EQUITY", "ETF"}

RESULT_LIMIT = 5  # top 5 suggestions, matching the news FETCH_LIMIT convention
# Ask Yahoo for well over RESULT_LIMIT: the filters above discard most of what it
# returns (a search for "visa" yields Buenos Aires, Vienna and Bangkok listings before
# a second US match), so a tight upstream limit would starve the filtered list.
UPSTREAM_LIMIT = 25


class SymbolSearchError(Exception):
    pass


@dataclass
class SymbolMatch:
    symbol: str
    name: str
    region: str
    exchange: str  # human-readable, e.g. "NASDAQ" — for disambiguating in the UI
    quote_type: str  # 'EQUITY' | 'ETF'


def search_symbols(query: str) -> list[SymbolMatch]:
    """Matching US/HK/SG equities and ETFs, best match first (Yahoo's own ordering).
    An empty or whitespace query returns no results rather than querying upstream."""
    query = query.strip()
    if not query:
        return []

    try:
        quotes = yf.Search(query, max_results=UPSTREAM_LIMIT).quotes or []
    except Exception as exc:  # yfinance surfaces network/parse failures untyped
        raise SymbolSearchError(f"Symbol search unavailable: {exc}") from exc

    matches: list[SymbolMatch] = []
    for q in quotes:
        region = EXCHANGE_REGION.get(q.get("exchange") or "")
        if region is None or (q.get("quoteType") or "") not in TRADABLE_TYPES:
            continue
        symbol = q.get("symbol")
        if not symbol:
            continue
        matches.append(
            SymbolMatch(
                symbol=symbol,
                name=q.get("shortname") or q.get("longname") or symbol,
                region=region,
                exchange=q.get("exchDisp") or q.get("exchange") or "",
                quote_type=q["quoteType"],
            )
        )
        if len(matches) == RESULT_LIMIT:
            break

    return matches
