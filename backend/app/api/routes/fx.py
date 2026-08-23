from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.services.fx import FxRateUnavailableError, refresh_fx_rates

router = APIRouter(tags=["fx"])


class FxRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    currency_pair: str
    rate: float


@router.post("/fx-rates/refresh", response_model=list[FxRateResponse])
def refresh() -> list[FxRateResponse]:
    try:
        rows = refresh_fx_rates()
    except FxRateUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [FxRateResponse.model_validate(row) for row in rows]
