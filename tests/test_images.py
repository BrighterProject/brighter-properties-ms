# from unittest.mock import AsyncMock, MagicMock, patch
# from uuid import UUID
#
# from app.deps import CurrentUser
#
# from .factories import (
#     IMAGE_ID,
#     OWNER_ID,
#     PROPERTY_ID,
#     image_response,
#     make_admin,
#     make_user,
# )
#
#
# class TestPropertyImages:
#     def _client_with_property(
#         self, user: CurrentUser, build_app, property_owner_id: UUID = OWNER_ID
#     ):
#         """Patch get_property so ownership checks see the right owner."""
#         app = build_app(user)
#
#         async def _mock_get_property(_property_id):
#             return MagicMock(owner_id=property_owner_id)
#
#         # Patch at module level so _assert_owns_property resolves correctly
#         return app, _mock_get_property
#
#     def test_list_images_returns_200(self, client_factory):
#         with patch("property_router.property_image_crud") as mock:
#             mock.list_for_property = AsyncMock(return_value=[image_response()])
#             resp = client_factory(make_user()).get(f"/properties/{PROPERTY_ID}/images")
#         assert resp.status_code == 200
#         assert len(resp.json()) == 1
#
#     def test_add_image_by_owner(self, client_factory):
#         with (
#             patch("property_router.property_crud") as vcrud,
#             patch("property_router.property_image_crud") as icrud,
#         ):
#             vcrud.get_property = AsyncMock(return_value=MagicMock(owner_id=OWNER_ID))
#             icrud.create_for_property = AsyncMock(return_value=image_response())
#             resp = client_factory(make_user(user_id=OWNER_ID)).post(
#                 f"/properties/{PROPERTY_ID}/images",
#                 json={"url": "https://example.com/img.jpg", "order": 0},
#             )
#         assert resp.status_code == 201
#
#     def test_add_image_by_non_owner_gets_403(self, client_factory):
#         with patch("property_router.property_crud") as vcrud:
#             # Property is owned by OWNER_ID, but request comes from OTHER_USER_ID
#             vcrud.get_property = AsyncMock(return_value=MagicMock(owner_id=OWNER_ID))
#             resp = client_factory(make_user(user_id=OTHER_USER_ID)).post(
#                 f"/properties/{PROPERTY_ID}/images",
#                 json={"url": "https://example.com/img.jpg"},
#             )
#         assert resp.status_code == 403
#
#     def test_update_image(self):
#         with (
#             patch("property_router.property_crud") as vcrud,
#             patch("property_router.property_image_crud") as icrud,
#         ):
#             vcrud.get_property = AsyncMock(return_value=MagicMock(owner_id=OWNER_ID))
#             icrud.update = AsyncMock(return_value=image_response(is_thumbnail=True))
#             resp = client_factory(make_user()).patch(
#                 f"/properties/{PROPERTY_ID}/images/{IMAGE_ID}",
#                 json={"is_thumbnail": True},
#             )
#         assert resp.status_code == 200
#         assert resp.json()["is_thumbnail"] is True
#
#     def test_update_image_not_found_returns_404(self):
#         with (
#             patch("property_router.property_crud") as vcrud,
#             patch("property_router.property_image_crud") as icrud,
#         ):
#             vcrud.get_property = AsyncMock(return_value=MagicMock(owner_id=OWNER_ID))
#             icrud.update = AsyncMock(return_value=None)
#             resp = client_factory(make_user()).patch(
#                 f"/properties/{PROPERTY_ID}/images/{IMAGE_ID}",
#                 json={"order": 2},
#             )
#         assert resp.status_code == 404
#
#     def test_delete_image(self):
#         with (
#             patch("property_router.property_crud") as vcrud,
#             patch("property_router.property_image_crud") as icrud,
#         ):
#             vcrud.get_property = AsyncMock(return_value=MagicMock(owner_id=OWNER_ID))
#             icrud.delete = AsyncMock(return_value=True)
#             resp = client_factory(make_user()).delete(
#                 f"/properties/{PROPERTY_ID}/images/{IMAGE_ID}"
#             )
#         assert resp.status_code == 204
#
#     def test_delete_image_not_found(self):
#         with (
#             patch("property_router.property_crud") as vcrud,
#             patch("property_router.property_image_crud") as icrud,
#         ):
#             vcrud.get_property = AsyncMock(return_value=MagicMock(owner_id=OWNER_ID))
#             icrud.delete = AsyncMock(return_value=False)
#             resp = client_factory(make_user()).delete(
#                 f"/properties/{PROPERTY_ID}/images/{IMAGE_ID}"
#             )
#         assert resp.status_code == 404
#
#     def test_reorder_images(self):
#         ids = [str(uuid4()), str(uuid4())]
#         with (
#             patch("property_router.property_crud") as vcrud,
#             patch("property_router.property_image_crud") as icrud,
#         ):
#             vcrud.get_property = AsyncMock(return_value=MagicMock(owner_id=OWNER_ID))
#             icrud.reorder = AsyncMock(return_value=[image_response()])
#             resp = client_factory(make_user()).put(
#                 f"/properties/{PROPERTY_ID}/images/reorder", json=ids
#             )
#         assert resp.status_code == 200
#
#     def test_admin_can_manage_any_properties_images(self):
#         """Admin bypasses ownership check even on another owner's property."""
#         with (
#             patch("property_router.property_crud") as vcrud,
#             patch("property_router.property_image_crud") as icrud,
#         ):
#             vcrud.get_property = AsyncMock(return_value=MagicMock(owner_id=OWNER_ID))
#             icrud.create_for_property = AsyncMock(return_value=image_response())
#             resp = client_factory(make_admin()).post(
#                 f"/properties/{PROPERTY_ID}/images",
#                 json={"url": "https://example.com/img.jpg"},
#             )
#         assert resp.status_code == 201
