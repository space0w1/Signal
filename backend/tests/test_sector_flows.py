from datetime import date, timedelta

from app.services.sector_flows import SECTORS, FundDay, _snapshot, daily_flows


def _days(rows: list[tuple[float, float]], start: date = date(2025, 12, 29)) -> list[FundDay]:
    """(nav, shares) per consecutive day; assets = nav * shares."""
    return [FundDay(start + timedelta(days=i), nav, shares, nav * shares) for i, (nav, shares) in enumerate(rows)]


def test_flow_is_share_change_times_nav():
    days = _days([(100, 1000), (101, 1010), (99, 1005)])
    assert daily_flows(days) == [10 * 101, -5 * 99]


def test_split_day_is_not_a_flow():
    # 2-for-1 split on day 2, then a genuine creation of 20 shares.
    days = _days([(100, 1000), (50, 2000), (51, 2020)])
    assert daily_flows(days) == [0.0, 20 * 51]


def test_snapshot_periods():
    # 2025-12-29, 12-30, 12-31, then 2026-01-01 .. 01-03
    days = _days([(100, 1000), (100, 1000), (100, 1100), (110, 1100), (110, 1150), (121, 1150)])
    snap = _snapshot(SECTORS[0], days)

    one_day = snap.periods["1d"]
    assert one_day.flow == 0
    assert round(one_day.change, 6) == 10.0

    # YTD starts from 2025-12-31's close: +50 shares at NAV 110.
    ytd = snap.periods["ytd"]
    assert ytd.flow == 50 * 110
    assert round(ytd.flow_pct, 6) == round(50 * 110 / (100 * 1100) * 100, 6)
    assert round(ytd.change, 6) == 21.0

    # Not enough history for 21 sessions back.
    assert snap.periods["1m"].flow is None
