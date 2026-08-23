# API Reference

## External Dependencies (not APIs you build — libraries/services you call)

| Service | Used for | Auth needed |
|---|---|---|
| `yfinance` (Python library) | Current price, 5yr historical price, FX rates (USD→SGD, HKD→SGD), news per ticker | None — no signup, no key |
| Anthropic API | Nightly + on-demand summary generation (portfolio-level and per-stock prompts, structured output) | API key (env var) |

No other third-party APIs are needed — this was previously going to include Twelve Data and/or iTick, but both were dropped once yfinance was confirmed to cover US, HK, and SG.

---

## Internal REST API (backend you build in Phase 8)

Bound to your Tailscale interface only. No auth (single user, Tailscale gates access).

### Portfolio & Stock Data

| Method | Path | Query params | Returns |
|---|---|---|---|
| GET | `/api/portfolio` | `date` (optional, defaults to today) | Aggregate portfolio value + PnL, and the holdings list sorted by PnL descending (powers both the Value/PnL box and the "View Stocks" toggle in Portfolio mode) |
| GET | `/api/stock/<ticker>` | `date` (optional) | That stock's current price × qty, cost basis × qty, PnL amount + % |

### Graph

| Method | Path | Query params | Returns |
|---|---|---|---|
| GET | `/api/graph/portfolio` | `date`, `mode=aggregate\|overlay` | `aggregate`: portfolio value over time (5yr), reconstructed honestly (stocks contribute $0 before their purchase date). `overlay`: all held stocks' normalized % return, plotted together |
| GET | `/api/graph/stock/<ticker>` | `date` (optional) | Single price line for that ticker, 5yr |

### Summary & News

| Method | Path | Query params | Returns |
|---|---|---|---|
| GET | `/api/summary` | `target=portfolio\|<ticker>`, `date` | Summary text. For `target=portfolio`, also includes the cited news items in relevance order. Checks the `summaries` cache first; if missing for that target/date, generates live (on-demand fallback), caches it, then returns it. |
| GET | `/api/news/stock/<ticker>` | — | Raw passthrough of that ticker's cached news (sourced from yfinance's `.news`), no cap, not tied to the summary's citations |

### Navigation Support (dropdown / date-picker constraints)

| Method | Path | Query params | Returns |
|---|---|---|---|
| GET | `/api/valid-tickers` | `date` | Tickers that existed in the portfolio as of that date — powers the dropdown when a date is selected |
| GET | `/api/valid-dates` | `ticker` | That ticker's valid date range (its own start date through today) — powers the date picker when a stock is selected |

### Portfolio Management (Modify Portfolio modal)

| Method | Path | Body / Query | Effect |
|---|---|---|---|
| POST | `/api/holdings` | body: `{ symbol, region, qty, cost }` (`region` is `US`\|`HK`\|`SG`, explicit — not guessed from the ticker suffix, since e.g. a typo'd `.SG` instead of `.SI` silently produced a wrong-currency holding) | Adds a new holding, or adds to an existing one (cumulative qty/cost) if the symbol's already held. Triggers 5yr backfill if it's a brand-new ticker. Fails with 422 if the ticker has no price data, or if `region` doesn't match the region the ticker was originally added under. |
| DELETE | `/api/holdings/<ticker>` | — | Soft-deletes the holding (excluded from current views, history preserved for past date-picker snapshots) |
| POST | `/api/price-history/<ticker>/backfill` | query: `region` | Standalone 5yr price backfill for a ticker, independent of adding a holding — useful for retrying after fixing a wrong symbol. Fails with 422 if the ticker has no price data. |

### FX Rates

| Method | Path | Body / Query | Effect |
|---|---|---|---|
| POST | `/api/fx-rates/refresh` | — | Fetches today's spot USD→SGD and HKD→SGD rates (yfinance `USDSGD=X` / `HKDSGD=X`) and upserts them into `fx_rates`. This is what the nightly cron (README section "Nightly Schedule") calls; safe to call more than once a day — re-running just overwrites today's row. Fails with 502 if yfinance has no rate for a pair. |

---

## Notes

- Every endpoint above reads from data the nightly cron already computed, **except** the on-demand fallback in `/api/summary` (fires only for stock/date combos not yet cached) and `POST/DELETE /api/holdings` (which write directly).
- `add_holding()` / `remove_holding()` and `generate_summary()` are written once (Phase 4 / Phase 6) and called identically by both the CLI scripts and these API endpoints — no duplicated logic between the two interfaces.