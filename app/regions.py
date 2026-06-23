from __future__ import annotations

import json
import pathlib
from functools import lru_cache
from typing import TypedDict

_DATA_DIR = pathlib.Path(__file__).parent.parent / "processing"


class OblastEntry(TypedDict):
    code: str
    name: str
    name_en: str


class SettlementEntry(TypedDict):
    ekatte: str
    tvm: str
    name: str
    name_en: str


@lru_cache(maxsize=1)
def _oblasts() -> list[OblastEntry]:
    raw: list[dict] = json.loads(
        (_DATA_DIR / "ek_obl.json").read_text(encoding="utf-8")
    )
    return [
        OblastEntry(code=e["oblast"], name=e["name"], name_en=e["name_en"])
        for e in raw
        if "oblast" in e
    ]


@lru_cache(maxsize=1)
def _settlements_by_oblast() -> dict[str, list[SettlementEntry]]:
    raw: dict = json.loads(
        (_DATA_DIR / "final_merged_settlements.json").read_text(encoding="utf-8")
    )
    return {
        code: [
            SettlementEntry(
                ekatte=s["ekatte"],
                tvm=s["tvm"],
                name=s["name"],
                name_en=s["name_en"],
            )
            for s in entries
        ]
        for code, entries in raw.items()
    }


@lru_cache(maxsize=1)
def _ekatte_index() -> dict[str, SettlementEntry]:
    idx: dict[str, SettlementEntry] = {}
    for entries in _settlements_by_oblast().values():
        for s in entries:
            idx[s["ekatte"]] = s
    return idx


def get_oblasts() -> list[OblastEntry]:
    return _oblasts()


def get_settlements(oblast_code: str) -> list[SettlementEntry]:
    return _settlements_by_oblast().get(oblast_code.upper(), [])


def get_settlement(ekatte: str) -> SettlementEntry | None:
    return _ekatte_index().get(ekatte)


def search_oblasts(q: str, lang: str, limit: int = 10) -> list[OblastEntry]:
    q_lower = q.lower()
    results: list[OblastEntry] = []
    for o in _oblasts():
        name = o["name_en"] if lang == "en" else o["name"]
        if q_lower in name.lower():
            results.append(o)
            if len(results) >= limit:
                break
    return results


def search_settlements(q: str, lang: str, limit: int = 10) -> list[SettlementEntry]:
    q_lower = q.lower()
    results: list[SettlementEntry] = []
    for entries in _settlements_by_oblast().values():
        for s in entries:
            name = s["name_en"] if lang == "en" else s["name"]
            if q_lower in name.lower():
                results.append(s)
                if len(results) >= limit:
                    return results
    return results


def resolve_city_name(ekatte: str | None, lang: str) -> str | None:
    if not ekatte:
        return None
    s = get_settlement(ekatte)
    if not s:
        return None
    return s["name_en"] if lang == "en" else s["name"]
