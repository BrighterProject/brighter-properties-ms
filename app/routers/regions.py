from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.regions import (
    get_oblasts,
    get_settlement,
    get_settlements,
    search_oblasts,
    search_settlements,
)
from app.settings import DEFAULT_LOCALE

router = APIRouter(prefix="/regions", tags=["regions"])


class OblastResponse(BaseModel):
    code: str
    name: str


class SettlementResponse(BaseModel):
    ekatte: str
    tvm: str | None
    name: str


class SettlementCenterResponse(BaseModel):
    """Approximate centroid of a settlement, for centering the map on selection.

    Coordinates are best-effort (see ``processing/geocode_settlements.py``) and
    may be ``None`` for the long tail of villages; clients fall back to the
    Sofia center in that case.
    """

    ekatte: str
    name: str
    lat: float | None
    lon: float | None


class DestinationResponse(BaseModel):
    """Unified search result: an oblast (region) or a settlement.

    `code` carries the value used to filter properties — the oblast `region_code`
    for oblasts, or the settlement `ekatte` for settlements.
    """

    kind: Literal["oblast", "settlement"]
    code: str
    name: str
    tvm: str | None = None


@router.get("/", response_model=list[OblastResponse])
async def list_oblasts(lang: str = Query(default=DEFAULT_LOCALE, max_length=5)):
    return [
        OblastResponse(
            code=o["code"],
            name=o["name_en"] if lang == "en" else o["name"],
        )
        for o in get_oblasts()
    ]


@router.get("/settlements/search", response_model=list[SettlementResponse])
async def search_settlements_endpoint(
    q: str = Query(min_length=1, max_length=100),
    lang: str = Query(default=DEFAULT_LOCALE, max_length=5),
    limit: int = Query(default=10, ge=1, le=50),
):
    return [
        SettlementResponse(
            ekatte=s["ekatte"],
            tvm=s["tvm"],
            name=s["name_en"] if lang == "en" else s["name"],
        )
        for s in search_settlements(q, lang, limit)
    ]


@router.get("/settlements/{ekatte}", response_model=SettlementCenterResponse)
async def get_settlement_center(
    ekatte: str,
    lang: str = Query(default=DEFAULT_LOCALE, max_length=5),
):
    """Return the approximate map center for a settlement by EKATTE code."""
    settlement = get_settlement(ekatte)
    if settlement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Settlement not found"
        )
    return SettlementCenterResponse(
        ekatte=settlement["ekatte"],
        name=settlement["name_en"] if lang == "en" else settlement["name"],
        lat=settlement.get("lat"),
        lon=settlement.get("lon"),
    )


@router.get("/search", response_model=list[DestinationResponse])
async def search_destinations(
    q: str = Query(min_length=1, max_length=100),
    lang: str = Query(default=DEFAULT_LOCALE, max_length=5),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Combined destination search returning matching oblasts then settlements."""
    oblasts = [
        DestinationResponse(
            kind="oblast",
            code=o["code"],
            name=o["name_en"] if lang == "en" else o["name"],
        )
        for o in search_oblasts(q, lang, limit)
    ]
    remaining = limit - len(oblasts)
    settlements = (
        [
            DestinationResponse(
                kind="settlement",
                code=s["ekatte"],
                name=s["name_en"] if lang == "en" else s["name"],
                tvm=s["tvm"],
            )
            for s in search_settlements(q, lang, remaining)
        ]
        if remaining > 0
        else []
    )
    return oblasts + settlements


@router.get("/{code}/settlements", response_model=list[SettlementResponse])
async def list_settlements(
    code: str,
    lang: str = Query(default=DEFAULT_LOCALE, max_length=5),
):
    return [
        SettlementResponse(
            ekatte=s["ekatte"],
            tvm=s["tvm"],
            name=s["name_en"] if lang == "en" else s["name"],
        )
        for s in get_settlements(code)
    ]
