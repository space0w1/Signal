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
-- One row per ticker per user. Cost basis is CUMULATIVE, not
-- lot-level (section 2.1) — total_quantity and total_cost are
-- running totals; average price is derived (total_cost /
-- total_quantity), never stored separately.
--
-- Soft-delete (section 2.9): removing a stock sets is_active=false
-- and stamps removed_date, rather than deleting the row. This
-- keeps past date-picker snapshots (section 2.8) honest — the
-- holding still existed on any date before removed_date.
-- ============================================================
CREATE TABLE holdings (
id             SERIAL PRIMARY KEY,
user_id        INTEGER NOT NULL REFERENCES users(id),
ticker         TEXT NOT NULL,               -- e.g. 'AAPL', '0700.HK', 'D05.SI'
exchange       TEXT NOT NULL,               -- 'US' | 'HK' | 'SG'
currency       TEXT NOT NULL,               -- 'USD' | 'HKD' | 'SGD'
total_quantity DOUBLE PRECISION NOT NULL,   -- cumulative shares held
total_cost     DOUBLE PRECISION NOT NULL,   -- cumulative cost basis (sum of price*qty), native currency
date_added     DATE NOT NULL,               -- date of first purchase
is_active      BOOLEAN NOT NULL DEFAULT TRUE, -- soft-delete flag: true = currently held, false = removed
removed_date   DATE,                        -- date soft-deleted; NULL while active
UNIQUE (user_id, ticker)
);

CREATE INDEX idx_holdings_active ON holdings (user_id, is_active);

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
-- Raw news per ticker, fetched nightly via yfinance's `.news`.
-- fetched_date ties each batch to the cron day it came in,
-- which keeps date-picker scoping possible even though the
-- individual-stock News panel now reads this table directly
-- (section 2.5) rather than going through a summary's citations.
-- ============================================================
CREATE TABLE news_items (
id           SERIAL PRIMARY KEY,
ticker       TEXT NOT NULL,
headline     TEXT NOT NULL,
source       TEXT,
url          TEXT,
published_at TIMESTAMP,          -- article's own publish timestamp, from yfinance
fetched_date DATE NOT NULL,      -- the cron run date this was pulled on
UNIQUE (ticker, url)             -- de-dupes re-fetched articles across nights
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
summary_text   TEXT NOT NULL,
cited_news_ids TEXT,               -- JSON array of news_items.id, ranked order; portfolio only
generated_at   TIMESTAMP NOT NULL, -- distinguishes nightly-cron vs on-demand-fallback generation
UNIQUE (user_id, target_type, ticker, date)
);
-- No separate lookup index needed: the UNIQUE constraint above already
-- covers lookups on (user_id, target_type, ticker, date).
```
