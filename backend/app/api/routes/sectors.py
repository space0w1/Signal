from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.sector_flows import (
    SectorFlowsUnavailableError,
    get_sector_flow_history,
    get_sector_flows,
    sync_sector_flows,
)

router = APIRouter(tags=["sectors"])


class SectorSyncResponse(BaseModel):
    rows_written: int


class SectorPeriodResponse(BaseModel):
    flow: float | None
    flow_pct: float | None
    change: float | None


class SectorFlowResponse(BaseModel):
    symbol: str
    name: str
    group: str
    as_of: date | None
    nav: float | None
    total_net_assets: float | None
    periods: dict[str, SectorPeriodResponse]
    stale: bool


class SectorFlowPoint(BaseModel):
    date: date
    cumulative_flow: float


@router.get("/sectors/flows", response_model=list[SectorFlowResponse])
def sector_flows() -> list[SectorFlowResponse]:
    """The 11 US sector ETFs with net money flows (USD) and NAV % change for
    1d/1w/1m/ytd, for the Sectors page. Reads stored NAV history; see
    POST /sectors/flows/refresh and the nightly job for updates."""
    try:
        snapshots = get_sector_flows()
    except SectorFlowsUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        SectorFlowResponse(
            symbol=s.sector.symbol,
            name=s.sector.name,
            group=s.sector.group,
            as_of=s.as_of,
            nav=s.nav,
            total_net_assets=s.total_net_assets,
            periods={
                p: SectorPeriodResponse(flow=v.flow, flow_pct=v.flow_pct, change=v.change)
                for p, v in s.periods.items()
            },
            stale=s.stale,
        )
        for s in snapshots
    ]


@router.get("/sectors/flows/{symbol}/history", response_model=list[SectorFlowPoint])
def sector_flow_history(symbol: str) -> list[SectorFlowPoint]:
    """Cumulative daily net flow for one sector ETF over roughly the last year."""
    try:
        history = get_sector_flow_history(symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown sector ETF {symbol}") from exc
    except SectorFlowsUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [SectorFlowPoint(date=d, cumulative_flow=total) for d, total in history]


@router.post("/sectors/flows/refresh", response_model=SectorSyncResponse)
def refresh_sector_flows() -> SectorSyncResponse:
    """Downloads each fund's NAV history from State Street and upserts it (2 years
    for a fund seen for the first time). The nightly job calls the same function."""
    try:
        rows_written = sync_sector_flows()
    except SectorFlowsUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SectorSyncResponse(rows_written=rows_written)
