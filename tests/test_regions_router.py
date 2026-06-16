"""Tests for the public /regions endpoints, including combined destination search."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.regions import search_oblasts
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
    items = _client().get(
        "/regions/search", params={"q": "sofia", "lang": "en"}
    ).json()
    first_settlement = next(
        (i for i, it in enumerate(items) if it["kind"] == "settlement"), len(items)
    )
    last_oblast = max(
        (i for i, it in enumerate(items) if it["kind"] == "oblast"), default=-1
    )
    assert last_oblast < first_settlement


def test_combined_search_shape() -> None:
    items = _client().get(
        "/regions/search", params={"q": "sofia", "lang": "en"}
    ).json()
    for item in items:
        assert set(item) == {"kind", "code", "name", "tvm"}
        if item["kind"] == "oblast":
            assert item["tvm"] is None


def test_combined_search_respects_limit() -> None:
    items = _client().get(
        "/regions/search", params={"q": "a", "lang": "en", "limit": 5}
    ).json()
    assert len(items) <= 5
