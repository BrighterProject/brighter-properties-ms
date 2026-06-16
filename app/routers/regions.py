from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.regions import (
    get_oblasts,
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
