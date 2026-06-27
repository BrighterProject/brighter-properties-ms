"""Tests for the public /regions endpoints, including combined destination search."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.regions import get_settlements, search_oblasts
from app.routers.regions import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_search_oblasts_matches_by_name() -> None:
    results = search_oblasts("sofia", "en", limit=10)
    assert results, "expected at least one oblast matching 'sofia'"
    assert all("sofia" in o["name_en"].lower() for o in results)


def test_search_oblasts_respects_limit() -> None:
    assert len(search_oblasts("a", "en", limit=3)) <= 3


def test_combined_search_returns_oblasts_and_settlements() -> None:
    resp = _client().get("/regions/search", params={"q": "sofia", "lang": "en"})
    assert resp.status_code == 200
    items = resp.json()
    kinds = {item["kind"] for item in items}
    assert "oblast" in kinds
    assert "settlement" in kinds


def test_combined_search_oblasts_listed_first() -> None:
    items = _client().get("/regions/search", params={"q": "sofia", "lang": "en"}).json()
    first_settlement = next(
        (i for i, it in enumerate(items) if it["kind"] == "settlement"), len(items)
    )
    last_oblast = max(
        (i for i, it in enumerate(items) if it["kind"] == "oblast"), default=-1
    )
    assert last_oblast < first_settlement


def test_combined_search_shape() -> None:
    items = _client().get("/regions/search", params={"q": "sofia", "lang": "en"}).json()
    for item in items:
        assert set(item) == {"kind", "code", "name", "tvm"}
        if item["kind"] == "oblast":
            assert item["tvm"] is None


def test_combined_search_respects_limit() -> None:
    items = (
        _client()
        .get("/regions/search", params={"q": "a", "lang": "en", "limit": 5})
        .json()
    )
    assert len(items) <= 5


def test_settlement_center_returns_coordinates() -> None:
    # Sofia (ekatte 68134) is a high-population match — must carry coordinates.
    resp = _client().get("/regions/settlements/68134")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ekatte"] == "68134"
    assert set(body) == {"ekatte", "name", "lat", "lon"}
    assert body["lat"] is not None and body["lon"] is not None
    # Roughly within Bulgaria's bounding box.
    assert 41.0 <= body["lat"] <= 44.5
    assert 22.0 <= body["lon"] <= 28.5


def test_settlement_center_unknown_ekatte_is_404() -> None:
    resp = _client().get("/regions/settlements/00000")
    assert resp.status_code == 404


def test_settlement_center_does_not_shadow_search() -> None:
    # The static /settlements/search route must win over /settlements/{ekatte}.
    resp = _client().get("/regions/settlements/search", params={"q": "sofia"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_settlements_carry_coordinates() -> None:
    settlements = get_settlements("SFO")
    assert settlements, "expected settlements in the Sofia-grad oblast"
    assert all("lat" in s and "lon" in s for s in settlements)
