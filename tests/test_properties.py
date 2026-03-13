from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.schemas import PropertyResponse
from app.scopes import PropertyScope

from .factories import (
    OWNER_ID,
    PROPERTY_ID,
    make_admin,
    make_user,
    property_list_item,
    property_response,
)


class TestListProperties:
    def test_returns_200(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.list_properties = AsyncMock(return_value=[property_list_item()])
            resp = client_factory(make_user()).get("/properties")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_empty_list(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.list_properties = AsyncMock(return_value=[])
            resp = client_factory(make_user()).get("/properties")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filters_forwarded(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.list_properties = AsyncMock(return_value=[])
            resp = client_factory(make_user()).get(
                "/properties", params={"city": "Sofia", "is_indoor": True, "page": 2}
            )
        assert resp.status_code == 200
        call_filters = mock_crud.list_properties.call_args[0][0]
        assert call_filters.city == "Sofia"
        assert call_filters.is_indoor is True
        assert call_filters.page == 2


class TestGetProperty:
    def test_existing_property_returns_200(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.get_property = AsyncMock(return_value=property_response())
            resp = client_factory(make_user()).get(f"/properties/{PROPERTY_ID}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(PROPERTY_ID)

    def test_missing_property_returns_404(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.get_property = AsyncMock(return_value=None)
            resp = client_factory(make_user()).get(f"/properties/{PROPERTY_ID}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Property not found"


class TestCreateProperty:
    PAYLOAD = {
        "name": "Tennis Club Sofia",
        "description": "A great place for tennis lovers.",
        "address": "1 Sports Ave",
        "city": "Sofia",
        "price_per_hour": "25.00",
        "sport_types": ["tennis"],
    }

    def test_owner_can_create(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.create_property = AsyncMock(return_value=property_response())
            resp = client_factory(make_user()).post("/properties", json=self.PAYLOAD)
        assert resp.status_code == 201
        mock_crud.create_property.assert_awaited_once()

    def test_owner_id_injected_from_auth(self, client_factory):
        """owner_id must come from the token, not the request body."""
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.create_property = AsyncMock(return_value=property_response())
            client_factory(make_user(user_id=OWNER_ID)).post(
                "/properties", json=self.PAYLOAD
            )
        _, kwargs = mock_crud.create_property.call_args
        assert kwargs["owner_id"] == OWNER_ID

    def test_invalid_payload_returns_422(self, client_factory):
        resp = client_factory(make_user()).post("/properties", json={"name": "X"})
        assert resp.status_code == 422

    def test_user_without_write_scope_gets_403(self, anon_app):
        from app.deps import get_current_user

        async def _non_admin_user():
            return make_user(scopes=[PropertyScope.READ])

        anon_app.dependency_overrides[get_current_user] = _non_admin_user
        with TestClient(anon_app) as c:
            resp = c.post("/properties", json=self.PAYLOAD)

        assert resp.status_code == 403


class TestUpdateProperty:
    PATCH = {"name": "Renamed Court"}

    def test_owner_can_update_own_property(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.update_property = AsyncMock(
                return_value=property_response(name="Renamed Court")
            )
            resp = client_factory(make_user()).patch(
                f"/properties/{PROPERTY_ID}", json=self.PATCH
            )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Court"

    def test_returns_404_when_not_owner(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.update_property = AsyncMock(return_value=None)
            resp = client_factory(make_user()).patch(
                f"/properties/{PROPERTY_ID}", json=self.PATCH
            )
        assert resp.status_code == 404

    def test_admin_bypasses_ownership(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            existing = PropertyResponse(**property_response())
            mock_crud.get_property = AsyncMock(return_value=existing)
            mock_crud.update_property = AsyncMock(
                return_value=property_response(name="Admin Edit")
            )
            resp = client_factory(make_admin()).patch(
                f"/properties/{PROPERTY_ID}", json=self.PATCH
            )
        assert resp.status_code == 200
        # Admin path calls get_property first to resolve owner_id
        mock_crud.get_property.assert_awaited_once_with(PROPERTY_ID)

    def test_admin_404_when_property_missing(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.get_property = AsyncMock(return_value=None)
            resp = client_factory(make_admin()).patch(
                f"/properties/{PROPERTY_ID}", json=self.PATCH
            )
        assert resp.status_code == 404


class TestUpdatePropertyStatus:
    def test_admin_can_change_status(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.update_status = AsyncMock(
                return_value=property_response(status="inactive")
            )
            resp = client_factory(make_admin()).patch(
                f"/properties/{PROPERTY_ID}/status", json={"status": "inactive"}
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    def test_invalid_status_returns_422(self, client_factory):
        resp = client_factory(make_admin()).patch(
            f"/properties/{PROPERTY_ID}/status", json={"status": "flying"}
        )
        assert resp.status_code == 422

    def test_non_admin_gets_403(self, anon_app):
        """Non-admin users should be rejected before the route handler runs."""
        from app.deps import get_current_user

        async def _non_admin_user():
            return make_user(scopes=[PropertyScope.READ])

        anon_app.dependency_overrides[get_current_user] = _non_admin_user

        with TestClient(anon_app) as client:
            resp = client.patch(
                f"/properties/{PROPERTY_ID}/status", json={"status": "inactive"}
            )

        assert resp.status_code == 403


class TestDeleteProperty:
    def test_owner_deletes_own_property(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.delete_property = AsyncMock(return_value=True)
            resp = client_factory(make_user()).delete(f"/properties/{PROPERTY_ID}")
        assert resp.status_code == 204

    def test_owner_404_when_not_found(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.delete_property = AsyncMock(return_value=False)
            resp = client_factory(make_user()).delete(f"/properties/{PROPERTY_ID}")
        assert resp.status_code == 404

    def test_admin_uses_admin_delete(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.admin_delete_property = AsyncMock(return_value=True)
            resp = client_factory(make_admin()).delete(f"/properties/{PROPERTY_ID}")
        assert resp.status_code == 204
        mock_crud.admin_delete_property.assert_awaited_once_with(PROPERTY_ID)
        mock_crud.delete_property.assert_not_called()

    def test_admin_404_when_not_found(self, client_factory):
        with patch("app.routers.property.property_crud") as mock_crud:
            mock_crud.admin_delete_property = AsyncMock(return_value=False)
            resp = client_factory(make_admin()).delete(f"/properties/{PROPERTY_ID}")
        assert resp.status_code == 404
