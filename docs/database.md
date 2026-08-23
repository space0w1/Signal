# Database Schema (PostgreSQL)

Target shape for the `peewee.Model` classes in `backend/app/models/` — this is a spec to
build those models against, not a migration that gets executed as-is.

Reflects requirements doc sections 2.1, 2.2, 2.4, 2.8, 2.9, and section 3.

```sql
-- ============================================================
-- users
-- Single user today, but everything else is keyed by user_id
-- so real multi-user support later is additive, not a rewrite.
-- ============================================================
CREATE TABLE users (
id         SERIAL PRIMARY KEY,
created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- ============================================================
-- holdings
-- One row per ticker per user. total_quantity/total_cost/realized_pnl
-- are a CACHE — derived by replaying this holding's `transactions`
-- (the source of truth) in chronological order using the average-
-- cost method — recomputed on every write, never mutated directly.
-- This cache exists so "current totals" don't require a replay on
-- every read.
--
-- Soft-delete (section 2.9): removing a stock — explicitly, or
-- automatically once a sell brings total_quantity to zero — sets
-- is_active=false and stamps removed_date, rather than deleting the
-- row. This keeps past date-picker snapshots (section 2.8) honest —
-- the holding still existed on any date before removed_date.
-- Re-adding a removed ticker resets date_added to today, starting a
-- fresh window — transactions from the earlier stint are excluded
-- from the cache (and from point-in-time queries) by the date_added
-- bound, not by deleting them.
-- ============================================================
CREATE TABLE holdings (
id             SERIAL PRIMARY KEY,
user_id        INTEGER NOT NULL REFERENCES users(id),
ticker         TEXT NOT NULL,               -- e.g. 'AAPL', '0700.HK', 'D05.SI'
exchange       TEXT NOT NULL,               -- 'US' | 'HK' | 'SG'
currency       TEXT NOT NULL,               -- 'USD' | 'HKD' | 'SGD'
total_quantity DOUBLE PRECISION NOT NULL,   -- cache: shares held in the current active window
total_cost     DOUBLE PRECISION NOT NULL,   -- cache: cost basis of shares still held, native currency
realized_pnl   DOUBLE PRECISION NOT NULL DEFAULT 0, -- cache: cumulative gain/loss from sells in the current window, native currency
date_added     DATE NOT NULL,               -- date of first transaction in the current active window
is_active      BOOLEAN NOT NULL DEFAULT TRUE, -- soft-delete flag: true = currently held, false = removed
removed_date   DATE,                        -- date soft-deleted; NULL while active
UNIQUE (user_id, ticker)
);

CREATE INDEX idx_holdings_active ON holdings (user_id, is_active);

-- ============================================================
-- transactions
-- One row per buy or sell — the source of truth for cost basis and
-- PnL. Lets a past-date portfolio query (section 2.8) replay only
-- the transactions that had happened by that date, instead of
-- applying the holding's current (possibly later, larger) totals
-- backward in time. Uses the average-cost method: a sell's
-- cost-basis reduction is based on the average cost immediately
-- before it (not the sell price — that only determines the
-- realized gain/loss on that sale), so replaying requires
-- chronological order, not a simple SUM. transaction_date defaults
-- to today when adding/selling, but can be explicitly backdated to
-- the real-world trade date — useful when adding a position you
-- already owned, so the graph/point-in-time queries have real
-- history to show instead of starting flat from today. Must be
-- on/after the holding's date_added and not in the future.
-- ============================================================
CREATE TABLE transactions (
id               SERIAL PRIMARY KEY,
holding_id       INTEGER NOT NULL REFERENCES holdings(id),
type             TEXT NOT NULL,             -- 'buy' | 'sell'
quantity         DOUBLE PRECISION NOT NULL, -- always positive; type determines direction
price            DOUBLE PRECISION NOT NULL, -- per-share, native currency
transaction_date DATE NOT NULL
);

CREATE INDEX idx_transactions_holding_date ON transactions (holding_id, transaction_date);

-- ============================================================
-- price_history
-- Daily close price per ticker. Backfilled 5yr ONCE when a
-- ticker is first added (section 2.2), then one row APPENDED
-- per ticker per night by cron — never re-fetched or trimmed,
-- so this table only grows over time.
-- ============================================================
CREATE TABLE price_history (
ticker      TEXT NOT NULL,
date        DATE NOT NULL,
close_price DOUBLE PRECISION NOT NULL,
currency    TEXT NOT NULL,
PRIMARY KEY (ticker, date)
);

-- ============================================================
-- fx_rates
-- One row per currency pair per day, refreshed once nightly
-- during cron (section 3) — not fetched live per page view.
-- SG holdings need no conversion; only USD->SGD and HKD->SGD
-- are tracked.
-- ============================================================
CREATE TABLE fx_rates (
date          DATE NOT NULL,
currency_pair TEXT NOT NULL,   -- 'USDSGD' | 'HKDSGD'
rate          DOUBLE PRECISION NOT NULL,
PRIMARY KEY (date, currency_pair)
);

-- ============================================================
-- news_items
-- Raw news per ticker, fetched via yfinance's `.news`. fetched_date
-- ties each batch to the day it came in — the SAME article can
-- appear on yfinance's feed across multiple days, and each of
-- those days gets its own row (unique per ticker+url+fetched_date,
-- NOT per ticker+url), so that querying a specific past date
-- returns exactly what was fetched that day, not a deduplicated
-- all-time list. This also keeps date-picker scoping possible even
-- though the individual-stock News panel reads this table directly
-- (section 2.5) rather than going through a summary's citations.
-- ============================================================
CREATE TABLE news_items (
id           SERIAL PRIMARY KEY,
ticker       TEXT NOT NULL,
headline     TEXT NOT NULL,
source       TEXT,
url          TEXT,
thumbnail_url TEXT,              -- smallest available thumbnail from yfinance, for the News panel's card
article_text TEXT,               -- full text extracted via trafilatura, best-effort; context for the AI summary
published_at TIMESTAMP,          -- article's own publish timestamp, from yfinance
fetched_date DATE NOT NULL,      -- the day this fetch ran on
UNIQUE (ticker, url, fetched_date) -- de-dupes only a same-day re-run, not re-fetches across days
);

CREATE INDEX idx_news_ticker_date ON news_items (ticker, fetched_date);

-- ============================================================
-- summaries
-- One row per (target, date) — NOT overwritten daily, because
-- the date picker (section 2.8) needs past snapshots retrievable.
-- target_type distinguishes the portfolio-level summary from a
-- single stock's summary.
--
-- cited_news_ids only applies to target_type='portfolio' now
-- (JSON array of news_items.id, in the order the LLM cited them)
-- — stock-level summaries no longer need a citation list since
-- the stock News panel reads news_items directly (section 2.5).
--
-- Note: SQL treats each NULL as distinct in a UNIQUE constraint,
-- so a NULL ticker wouldn't actually enforce one-row-per-date for
-- the portfolio target. Using the sentinel string '__portfolio__'
-- instead of NULL avoids that trap.
-- ============================================================
CREATE TABLE summaries (
id             SERIAL PRIMARY KEY,
user_id        INTEGER NOT NULL REFERENCES users(id),
target_type    TEXT NOT NULL,      -- 'portfolio' | 'stock'
ticker         TEXT NOT NULL,      -- actual ticker, or '__portfolio__' sentinel when target_type='portfolio'
date           DATE NOT NULL,
summary_text   TEXT NOT NULL,      -- "what happened" section
next_steps_text TEXT,              -- "what's next" section (risks/catalysts to watch, not advice)
cited_news_ids TEXT,               -- JSON array of news_items.id, ranked order; portfolio only
generated_at   TIMESTAMP NOT NULL, -- distinguishes nightly-cron vs on-demand-fallback generation
UNIQUE (user_id, target_type, ticker, date)
);
-- No separate lookup index needed: the UNIQUE constraint above already
-- covers lookups on (user_id, target_type, ticker, date).
```
