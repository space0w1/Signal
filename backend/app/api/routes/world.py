from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.world_markets import (
    WorldMarketsUnavailableError,
    get_world_markets,
    sync_world_markets,
)

router = APIRouter(tags=["world"])


class WorldSyncResponse(BaseModel):
    rows_written: int


class WorldMarketResponse(BaseModel):
    country: str
    iso_n3: str
    symbol: str
    index_name: str
    currency: str
    kind: str
    lat: float
    lng: float
    last_close: float | None
    as_of: date | None
    change_1d: float | None
    change_1w: float | None
    change_1m: float | None
    change_ytd: float | None
    stale: bool


@router.get("/world/markets", response_model=list[WorldMarketResponse])
def world_markets() -> list[WorldMarketResponse]:
    """Headline stock market per country with 1D/1W/1M/YTD % changes, for the
    World page's globe. Changes are in each market's own currency. Reads stored
    closes; see POST /world/markets/refresh and the nightly job for updates."""
    try:
        snapshots = get_world_markets()
    except WorldMarketsUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        WorldMarketResponse(
            country=s.market.country,
            iso_n3=s.market.iso_n3,
            symbol=s.market.symbol,
            index_name=s.market.index_name,
            currency=s.market.currency,
            kind=s.market.kind,
            lat=s.market.lat,
            lng=s.market.lng,
            last_close=s.last_close,
            as_of=s.as_of,
            change_1d=s.change_1d,
            change_1w=s.change_1w,
            change_1m=s.change_1m,
            change_ytd=s.change_ytd,
            stale=s.stale,
        )
        for s in snapshots
    ]


@router.post("/world/markets/refresh", response_model=WorldSyncResponse)
def refresh_world_markets() -> WorldSyncResponse:
    """Fetches the latest closes from Yahoo and upserts them (2 years for a market
    seen for the first time). The nightly job calls the same function."""
    try:
        rows_written = sync_world_markets()
    except WorldMarketsUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return WorldSyncResponse(rows_written=rows_written)
