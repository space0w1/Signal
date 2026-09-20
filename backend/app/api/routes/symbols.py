from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.services.symbols import RESULT_LIMIT, SymbolSearchError, search_symbols

router = APIRouter(tags=["symbols"])


class SymbolMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    region: str
    exchange: str
    quote_type: str


@router.get("/symbols/search", response_model=list[SymbolMatchResponse])
def symbol_search(
    q: str = Query(..., min_length=1, max_length=64, description="Company name or ticker"),
) -> list[SymbolMatchResponse]:
    """Up to RESULT_LIMIT matching US/HK/SG equities and ETFs, so the Modify Portfolio
    form can offer real symbols with their region pre-filled instead of relying on the
    user typing an exact ticker and picking the right region by hand."""
    try:
        matches = search_symbols(q)
    except SymbolSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [SymbolMatchResponse.model_validate(m) for m in matches]
