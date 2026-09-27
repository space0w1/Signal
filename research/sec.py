"""SEC insider-transaction data sets -> one clean table of open-market purchases.

Source: https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets
One zip per quarter (2006q1 onward), published shortly after each quarter ends.
Only three of its tables are needed:

    NONDERIV_TRANS  the trades (code P = open-market purchase)
    SUBMISSION      issuer + ticker + FILING_DATE (when the public could see it)
    REPORTINGOWNER  who filed, and their role

All three join on ACCESSION_NUMBER, which identifies a *filing*; one filing can
carry several trades and several owners (e.g. a fund, its GP and the person
behind them), so owners are grouped per filing before joining to avoid counting
one purchase several times.
"""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path

import duckdb
import requests

INDEX_URL = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
TABLES = ("SUBMISSION", "REPORTINGOWNER", "NONDERIV_TRANS")

# Owner names that look like funds/companies rather than people. Such owners
# often hold board seats (so they show up as "Director"), but they're a
# different signal from an executive buying with their own money.
ENTITY_PATTERN = (
    r"\b(L\.?P\.?|L\.?L\.?C\.?|INC\.?|CORP\.?|CORPORATION|FUND|HOLDINGS?|TRUST|"
    r"PARTNERS|CAPITAL|LTD\.?|LIMITED|GROUP|MANAGEMENT|ADVISORS|FOUNDATION|PLC|N\.?V\.?)\b"
)
# Non-derivative table still contains the odd preferred/unit/note line.
EXCLUDED_TITLE_PATTERN = r"\b(preferred|notes?|debentures?|warrants?|units?|rights?)\b"


def _user_agent() -> str:
    # The SEC blocks requests without a descriptive User-Agent that includes contact info.
    ua = os.environ.get("SEC_USER_AGENT", "")
    if "@" not in ua:
        raise RuntimeError('Set SEC_USER_AGENT to something like "signal-research you@example.com"')
    return ua


def quarter_range(start: str, end: str) -> list[str]:
    """quarter_range("2024q3", "2025q2") -> ["2024q3", "2024q4", "2025q1", "2025q2"]"""
    sy, sq = int(start[:4]), int(start[-1])
    ey, eq = int(end[:4]), int(end[-1])
    out = []
    y, q = sy, sq
    while (y, q) <= (ey, eq):
        out.append(f"{y}q{q}")
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def available_quarters() -> dict[str, str]:
    """Scrape the index page for {quarter: zip url}. The newest quarter lives
    under a different path than older ones, so links aren't hard-coded."""
    html = requests.get(INDEX_URL, headers={"User-Agent": _user_agent()}, timeout=30).text
    links = re.findall(r'href="([^"]*/(\d{4}q[1-4])_form345\.zip)"', html)
    return {q: "https://www.sec.gov" + href for href, q in links}


def download_quarters(quarters: list[str], data_dir: Path) -> list[str]:
    """Download + extract the needed tables for each quarter into
    data_dir/<quarter>/. Already-extracted quarters are skipped. Returns the
    quarters that are available locally."""
    data_dir.mkdir(parents=True, exist_ok=True)
    urls = None
    ready = []
    for q in quarters:
        qdir = data_dir / q
        if all((qdir / f"{t}.tsv").exists() for t in TABLES):
            ready.append(q)
            continue
        if urls is None:
            urls = available_quarters()
        if q not in urls:
            print(f"{q}: not published yet, skipping")
            continue
        zip_path = data_dir / f"{q}_form345.zip"
        print(f"{q}: downloading")
        resp = requests.get(urls[q], headers={"User-Agent": _user_agent()}, timeout=300)
        resp.raise_for_status()
        zip_path.write_bytes(resp.content)
        with zipfile.ZipFile(zip_path) as zf:
            qdir.mkdir(exist_ok=True)
            for t in TABLES:
                (qdir / f"{t}.tsv").write_bytes(zf.read(f"{t}.tsv"))
        zip_path.unlink()
        ready.append(q)
    return ready


def build_purchases(quarters: list[str], data_dir: Path, out_path: Path) -> duckdb.DuckDBPyRelation:
    """Join the three tables across all quarters into one row per purchase
    and write it to Parquet. Returns the result as a DuckDB relation."""
    con = duckdb.connect()

    def view(table: str) -> None:
        files = [str(data_dir / q / f"{table}.tsv") for q in quarters]
        # all_varchar + quote='' : the files are plain TSV with literal quotes in text
        # union_by_name: newer years add columns (e.g. AFF10B5ONE from 2023)
        con.execute(
            f"CREATE VIEW {table} AS SELECT * FROM read_csv({files!r}, delim='\t', header=true, "
            f"all_varchar=true, quote='', union_by_name=true)"
        )

    for t in TABLES:
        view(t)

    # The ticker is free text typed by the filer: "NASDAQ:SVC", "[SSTI]", "NWIN(OB)",
    # "ISCA, ISCB", "N/A". Strip exchange prefixes/brackets and take the first symbol.
    con.execute("""
        CREATE MACRO clean_ticker(x) AS (
            WITH c AS (SELECT regexp_split_to_array(trim(regexp_replace(regexp_replace(regexp_replace(
                    upper(trim(x)), '^[A-Z ]+:[ ]*', ''), '[\\[\\]]', '', 'g'), '\\(.*?\\)', '', 'g')),
                    '[,; ]+')[1] AS t)
            SELECT CASE WHEN t IN ('', 'N/A', 'NA', 'N.A.', 'NONE') THEN NULL ELSE t END FROM c
        )
    """)

    rel = con.sql(f"""
        WITH owners AS (
            SELECT
                ACCESSION_NUMBER,
                -- a few filings (seen in 2021) leave the owner name blank
                coalesce(string_agg(DISTINCT RPTOWNERNAME, '; '), '(name missing)') AS owner_names,
                string_agg(DISTINCT RPTOWNERCIK, ';')                         AS owner_ciks,
                string_agg(DISTINCT nullif(trim(RPTOWNER_TITLE), ''), '; ')   AS owner_titles,
                count(DISTINCT RPTOWNERCIK)                                   AS n_owners,
                bool_or(RPTOWNER_RELATIONSHIP ILIKE '%officer%')              AS is_officer,
                bool_or(RPTOWNER_RELATIONSHIP ILIKE '%director%')             AS is_director,
                bool_or(RPTOWNER_RELATIONSHIP ILIKE '%tenpercent%')           AS is_ten_pct_owner,
                -- entity only if *every* owner on the filing looks like one
                coalesce(bool_and(regexp_matches(upper(RPTOWNERNAME), '{ENTITY_PATTERN}')), false) AS is_entity
            FROM REPORTINGOWNER
            GROUP BY 1
        ),
        trades AS (
            SELECT
                t.ACCESSION_NUMBER AS accession,
                -- position within the filing; the live EDGAR parser numbers
                -- transactions the same way so both sources dedupe on (accession, idx)
                row_number() OVER (PARTITION BY t.ACCESSION_NUMBER
                                   ORDER BY t.NONDERIV_TRANS_SK::BIGINT) AS trans_idx,
                t.SECURITY_TITLE AS security_title,
                try_strptime(t.TRANS_DATE, '%d-%b-%Y')::DATE AS trans_date,
                try_cast(t.TRANS_SHARES AS DOUBLE) AS shares,
                try_cast(t.TRANS_PRICEPERSHARE AS DOUBLE) AS price,
                try_cast(t.SHRS_OWND_FOLWNG_TRANS AS DOUBLE) AS shares_after,
                t.TRANS_TIMELINESS = 'L' AS is_late
            FROM NONDERIV_TRANS t
            WHERE t.TRANS_CODE = 'P' AND t.TRANS_ACQUIRED_DISP_CD = 'A'
        )
        SELECT
            tr.accession,
            tr.trans_idx,
            s.ISSUERCIK AS issuer_cik,
            s.ISSUERNAME AS issuer_name,
            clean_ticker(s.ISSUERTRADINGSYMBOL) AS ticker,
            try_strptime(s.FILING_DATE, '%d-%b-%Y')::DATE AS filing_date,
            -- Typos exist ("0024-05-15", trades dated after their own filing): blank
            -- those rather than drop the row, since signals only use filing_date.
            CASE WHEN tr.trans_date BETWEEN DATE '1990-01-01'
                                        AND try_strptime(s.FILING_DATE, '%d-%b-%Y')::DATE
                 THEN tr.trans_date END AS trans_date,
            tr.security_title,
            tr.shares,
            tr.price,
            tr.shares * tr.price AS value_usd,
            tr.shares_after,
            -- % increase of the insider's holding; NULL when it's a brand-new position
            CASE WHEN tr.shares_after > tr.shares
                 THEN tr.shares / (tr.shares_after - tr.shares) END AS stake_increase,
            coalesce(s.AFF10B5ONE IN ('1', 'true'), false) AS is_10b5_1,  -- only reported from 2023
            coalesce(tr.is_late, false) AS is_late,
            o.owner_names, o.owner_ciks, o.owner_titles, o.n_owners,
            o.is_officer, o.is_director, o.is_ten_pct_owner, o.is_entity,
            regexp_matches(upper(coalesce(o.owner_titles, '')),
                           '\\b(CEO|CFO)\\b|CHIEF EXECUTIVE|CHIEF FINANCIAL') AS is_ceo_cfo
        FROM trades tr
        JOIN SUBMISSION s ON s.ACCESSION_NUMBER = tr.accession
        JOIN owners o ON o.ACCESSION_NUMBER = tr.accession
        WHERE s.DOCUMENT_TYPE = '4'
          AND tr.shares > 0 AND tr.price > 0
          AND NOT regexp_matches(lower(coalesce(tr.security_title, '')), '{EXCLUDED_TITLE_PATTERN}')
        ORDER BY filing_date, accession, trans_idx
    """)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rel.write_parquet(str(out_path))
    return con.read_parquet(str(out_path))


def load_purchases(path: Path):
    """Read the Parquet written by build_purchases as a pandas DataFrame with datetime columns."""
    import pandas as pd

    df = pd.read_parquet(path)
    for col in ("filing_date", "trans_date"):
        df[col] = pd.to_datetime(df[col])
    # Filters negate these with ~, which fails on NULL; missing means "not flagged".
    for col in [c for c in df.columns if c.startswith("is_")]:
        df[col] = df[col].fillna(False).astype(bool)
    return df


FRAMES_URL = "https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/CY{year}Q{q}I.json"


def fetch_shares_outstanding(start_year: int, end_year: int, out_path: Path):
    """Shares outstanding per company over time, from the cover page of 10-K/10-Q
    filings (XBRL "frames" API: one request returns every company for a quarter).
    Quarters older than ~6 months are cached for good; recent ones are refetched
    each run since companies are still filing for them. Returns a
    DataFrame[cik, as_of, shares]."""
    import json

    import pandas as pd

    raw_dir = out_path.parent / "shares_frames"
    raw_dir.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp.today()
    for year in range(start_year, end_year + 1):
        for q in range(1, 5):
            quarter_end = pd.Timestamp(year=year, month=3 * q, day=1) + pd.offsets.MonthEnd(0)
            if quarter_end > today:
                continue  # not reported yet
            f = raw_dir / f"CY{year}Q{q}I.json"
            # Companies keep filing for ~6 months after a quarter ends, so recent
            # quarters are refetched; older ones are final and stay cached.
            if f.exists() and today - quarter_end > pd.Timedelta(days=180):
                continue
            resp = requests.get(FRAMES_URL.format(year=year, q=q),
                                headers={"User-Agent": _user_agent()}, timeout=60)
            if resp.status_code == 404:
                continue  # quarter not reported yet
            resp.raise_for_status()
            f.write_text(resp.text)

    rows = []
    for f in sorted(raw_dir.glob("*.json")):
        for r in json.loads(f.read_text())["data"]:
            rows.append((r["cik"], r["end"], r["val"]))
    df = pd.DataFrame(rows, columns=["cik", "as_of", "shares"])
    df["as_of"] = pd.to_datetime(df["as_of"])
    df = df[df["shares"] > 0].drop_duplicates(["cik", "as_of"]).sort_values("as_of")
    df.to_parquet(out_path)
    print(f"{len(df):,} share counts for {df.cik.nunique():,} companies")
    return df
