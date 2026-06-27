"""Generate ``ekatte_coords.json``: EKATTE settlement code -> approximate centroid.

One-off, offline, reproducible pipeline. Matches NSI/EKATTE settlements against
the GeoNames Bulgaria dump (``processing/BG.zip``) to assign each settlement an
approximate ``lat``/``lon`` used to center the map when an owner picks a
settlement. Accuracy only needs to be "good enough to pan near" — the owner then
drags the pin to the exact building, so an oblast-centroid fallback is acceptable
for the long tail of unmatched villages.

Match tiers (first hit wins):
    1. Cyrillic name within the settlement's oblast (GeoNames ``admin1``)
    2. Transliterated ``name_en`` within the oblast
    3. Cyrillic name that is unique countrywide (no oblast ambiguity)
    4. Oblast centroid fallback (always in the correct region)

The GeoNames dump is not committed (see .gitignore). Re-download it with:
    curl -sO https://download.geonames.org/export/dump/BG.zip   # -> processing/BG.zip

Run:
    uv run python processing/geocode_settlements.py
"""

from __future__ import annotations

import json
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Final, TypedDict

from loguru import logger

_DATA_DIR: Final = Path(__file__).parent
_GEONAMES_ZIP: Final = _DATA_DIR / "BG.zip"
_GEONAMES_MEMBER: Final = "BG.txt"
_OBLAST_FILE: Final = _DATA_DIR / "ek_obl.json"
_SETTLEMENTS_FILE: Final = _DATA_DIR / "final_merged_settlements.json"
_OUTPUT_FILE: Final = _DATA_DIR / "ekatte_coords.json"

# NSI oblast code -> GeoNames admin1 code, for the ambiguous Sofia pair only.
# SFO = Sofia (stolitsa / city) -> "Sofia-Grad"; SOF = Sofia province -> "Sofia".
_SOFIA_OVERRIDE: Final[dict[str, str]] = {"SFO": "42", "SOF": "58"}

# GeoNames TSV column indices (see processing/BG.zip!readme.txt).
_COL_NAME: Final = 1
_COL_ASCIINAME: Final = 2
_COL_ALTNAMES: Final = 3
_COL_LAT: Final = 4
_COL_LON: Final = 5
_COL_FEATURE_CLASS: Final = 6
_COL_FEATURE_CODE: Final = 7
_COL_ADMIN1: Final = 10
_COL_POPULATION: Final = 14
_MIN_COLS: Final = 15

_CYRILLIC_RANGE: Final = ("Ѐ", "ӿ")


class Coord(TypedDict):
    lat: float
    lon: float


class _Candidate(TypedDict):
    pop: int
    lat: float
    lon: float


def _ascii_fold(value: str | None) -> str:
    """Lowercase and strip accents/non-ASCII for Latin name matching."""
    folded = unicodedata.normalize("NFKD", (value or "").strip().lower())
    return folded.encode("ascii", "ignore").decode("ascii")


def _cyrillic_fold(value: str | None) -> str:
    """Lowercase and normalize a Cyrillic name for matching."""
    return (value or "").strip().lower().replace("ё", "е")  # ё -> е


def _is_cyrillic(text: str) -> bool:
    return any(_CYRILLIC_RANGE[0] <= ch <= _CYRILLIC_RANGE[1] for ch in text)


def _load_geonames() -> tuple[
    dict[str, str], dict[str, Coord], dict[tuple[str, str], _Candidate], dict[str, list[_Candidate]]
]:
    """Parse the GeoNames dump.

    Returns:
        adm1_name_to_code: folded oblast name -> GeoNames admin1 code
        adm1_centroid: admin1 code -> centroid Coord
        scoped_index: (admin1, folded name) -> best (highest-population) candidate
        global_index: folded Cyrillic name -> all candidates (for uniqueness test)
    """
    adm1_name_to_code: dict[str, str] = {}
    adm1_centroid: dict[str, Coord] = {}
    scoped_index: dict[tuple[str, str], _Candidate] = {}
    global_index: dict[str, list[_Candidate]] = defaultdict(list)

    with zipfile.ZipFile(_GEONAMES_ZIP) as archive, archive.open(_GEONAMES_MEMBER) as stream:
        for raw in stream:
            cols = raw.decode("utf-8").rstrip("\n").split("\t")
            if len(cols) < _MIN_COLS:
                continue

            lat, lon = round(float(cols[_COL_LAT]), 6), round(float(cols[_COL_LON]), 6)

            if cols[_COL_FEATURE_CODE] == "ADM1":
                name = cols[_COL_NAME].replace("Oblast ", "").replace("-Grad", "").strip()
                adm1_name_to_code[_ascii_fold(name)] = cols[_COL_ADMIN1]
                adm1_centroid[cols[_COL_ADMIN1]] = Coord(lat=lat, lon=lon)
                continue

            if cols[_COL_FEATURE_CLASS] != "P":
                continue

            admin1 = cols[_COL_ADMIN1]
            try:
                population = int(cols[_COL_POPULATION] or 0)
            except ValueError:
                population = 0
            candidate = _Candidate(pop=population, lat=lat, lon=lon)

            variants = {_cyrillic_fold(cols[_COL_NAME]), _ascii_fold(cols[_COL_ASCIINAME])}
            cyrillic_variants: set[str] = set()
            for alt in cols[_COL_ALTNAMES].split(","):
                if _is_cyrillic(alt):
                    folded = _cyrillic_fold(alt)
                    variants.add(folded)
                    cyrillic_variants.add(folded)

            for variant in variants:
                if not variant:
                    continue
                key = (admin1, variant)
                existing = scoped_index.get(key)
                if existing is None or population > existing["pop"]:
                    scoped_index[key] = candidate

            for variant in cyrillic_variants:
                if variant:
                    global_index[variant].append(candidate)

    return adm1_name_to_code, adm1_centroid, scoped_index, global_index


def build_coords() -> tuple[dict[str, Coord], dict[str, int]]:
    """Build the EKATTE -> Coord map and per-tier hit counts."""
    oblasts: list[dict[str, str]] = json.loads(_OBLAST_FILE.read_text(encoding="utf-8"))
    settlements: dict[str, list[dict[str, str]]] = json.loads(
        _SETTLEMENTS_FILE.read_text(encoding="utf-8")
    )
    nsi_names = {o["oblast"]: o["name_en"] for o in oblasts if "oblast" in o}

    adm1_name_to_code, adm1_centroid, scoped_index, global_index = _load_geonames()
    nsi_to_admin1 = {
        code: _SOFIA_OVERRIDE.get(code) or adm1_name_to_code[_ascii_fold(name)]
        for code, name in nsi_names.items()
    }

    coords: dict[str, Coord] = {}
    tiers: dict[str, int] = defaultdict(int)

    for oblast_code, entries in settlements.items():
        admin1 = nsi_to_admin1[oblast_code]
        centroid = adm1_centroid[admin1]
        for entry in entries:
            ekatte = entry["ekatte"]
            cyr = _cyrillic_fold(entry["name"])

            scoped = scoped_index.get((admin1, cyr))
            if scoped is not None:
                coords[ekatte] = Coord(lat=scoped["lat"], lon=scoped["lon"])
                tiers["oblast_cyrillic"] += 1
                continue

            scoped = scoped_index.get((admin1, _ascii_fold(entry["name_en"])))
            if scoped is not None:
                coords[ekatte] = Coord(lat=scoped["lat"], lon=scoped["lon"])
                tiers["oblast_translit"] += 1
                continue

            # Only trust a cross-oblast match when the name is unique countrywide,
            # otherwise we risk placing the pin in the wrong region.
            global_hits = global_index.get(cyr, [])
            unique_places = {(c["lat"], c["lon"]) for c in global_hits}
            if len(unique_places) == 1:
                best = global_hits[0]
                coords[ekatte] = Coord(lat=best["lat"], lon=best["lon"])
                tiers["unique_global"] += 1
                continue

            coords[ekatte] = Coord(lat=centroid["lat"], lon=centroid["lon"])
            tiers["oblast_centroid"] += 1

    return coords, dict(tiers)


def main() -> None:
    coords, tiers = build_coords()
    _OUTPUT_FILE.write_text(
        json.dumps(coords, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    total = sum(tiers.values())
    precise = total - tiers.get("oblast_centroid", 0)
    logger.info("Wrote {} settlement coordinates to {}", total, _OUTPUT_FILE.name)
    for tier, count in tiers.items():
        logger.info("  {:18} {:5}  {:5.1f}%", tier, count, 100 * count / total)
    logger.info(
        "Precise point matches: {} ({:.1f}%) | oblast-centroid fallback: {} ({:.1f}%)",
        precise,
        100 * precise / total,
        tiers.get("oblast_centroid", 0),
        100 * tiers.get("oblast_centroid", 0) / total,
    )


if __name__ == "__main__":
    main()
