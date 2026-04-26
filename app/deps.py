from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import quote, unquote
from uuid import UUID

import httpx
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger

from app import settings
from app.scopes import PROPERTY_SCOPE_DESCRIPTIONS, PropertyScope

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.users_ms_url}/auth/token",
    scopes={
        "users:read": "Read users data.",
        "users:me": "Read current user profile.",
        "admin:scopes": "Manage user scopes.",
        **PROPERTY_SCOPE_DESCRIPTIONS,
    },
)


@dataclass
class CurrentUser:
    id: UUID
    username: str
    scopes: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return "admin:scopes" in self.scopes


@lru_cache(maxsize=1)
def _get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.users_ms_url,
        timeout=httpx.Timeout(5.0),
    )


def get_current_user(
    x_user_id: str = Header(...),
    x_username: str = Header(...),
    x_user_scopes: str = Header(default=""),
) -> CurrentUser:
    """
    Reads the headers injected by Traefik after forwardAuth validation.
    The JWT has already been verified — we just trust these headers.
    NOTE: This only works behind Traefik. Run with that assumption.
    """
    try:
        user_id = UUID(x_user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity from gateway",
        ) from None

    scopes = x_user_scopes.split(" ") if x_user_scopes else []

    return CurrentUser(id=user_id, username=unquote(x_username), scopes=scopes)


def require_scopes(*required: str):
    """
    Factory that returns a dependency enforcing one or more scopes.

    Usage:
        @router.get("/admin-only")
        async def admin_route(user = Depends(require_scopes("admin:scopes"))):
            ...
    """

    async def _dep(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        missing = [s for s in required if s not in current_user.scopes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scopes: {', '.join(missing)}",
            )
        return current_user

    return _dep


async def require_admin(
    current_user: CurrentUser = Depends(require_scopes("admin:scopes")),
) -> CurrentUser:
    """Shorthand for admin-only endpoints."""
    return current_user


can_read_properties = require_scopes(PropertyScope.READ)
can_read_own_properties = require_scopes(PropertyScope.ME)
can_write_property = require_scopes(PropertyScope.WRITE)
can_delete_property = require_scopes(PropertyScope.DELETE)
can_manage_images = require_scopes(PropertyScope.IMAGES)
can_manage_schedule = require_scopes(PropertyScope.SCHEDULE)
can_admin_read = require_scopes(PropertyScope.ADMIN_READ)
can_admin_write = require_scopes(
    PropertyScope.ADMIN, PropertyScope.ADMIN_READ, PropertyScope.ADMIN_WRITE
)
can_admin_delete = require_scopes(
    PropertyScope.ADMIN,
    PropertyScope.ADMIN_READ,
    PropertyScope.ADMIN_WRITE,
    PropertyScope.ADMIN_DELETE,
)


def _owner_or_admin(owner_scope: PropertyScope, admin_scope: PropertyScope):
    """
    Returns a dependency that passes if the user has EITHER:
      - the owner-level scope, OR
      - the admin-level scope
    Raises 403 otherwise.
    """

    async def _dep(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        has_owner = owner_scope in current_user.scopes
        has_specific_admin = admin_scope in current_user.scopes
        has_admin = PropertyScope.ADMIN in current_user.scopes

        if not (has_owner or has_specific_admin or has_admin):
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Requires '{owner_scope}' (for your own properties) "
                    f"or '{admin_scope}' (admin)."
                ),
            )
        return current_user

    return _dep


can_write_or_admin = _owner_or_admin(PropertyScope.WRITE, PropertyScope.ADMIN_WRITE)
can_delete_or_admin = _owner_or_admin(PropertyScope.DELETE, PropertyScope.ADMIN_DELETE)
can_images_or_admin = _owner_or_admin(PropertyScope.IMAGES, PropertyScope.ADMIN_WRITE)
can_schedule_or_admin = _owner_or_admin(PropertyScope.SCHEDULE, PropertyScope.ADMIN_WRITE)


# ---------------------------------------------------------------------------
# System identity for internal service-to-service calls (notifications)
# ---------------------------------------------------------------------------

_SYSTEM_ADMIN: "CurrentUser | None" = None


def _get_system_admin() -> "CurrentUser":
    global _SYSTEM_ADMIN
    if _SYSTEM_ADMIN is None:
        _SYSTEM_ADMIN = CurrentUser(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            username="properties-ms",
            scopes=["admin:scopes", "admin:notifications:write"],
        )
    return _SYSTEM_ADMIN


# ---------------------------------------------------------------------------
# UsersClient — fetch user data for notification email resolution
# ---------------------------------------------------------------------------


class UsersClient:
    @property
    def _client(self) -> httpx.AsyncClient:
        return _get_http_client()

    def _headers(self) -> dict[str, str]:
        admin = _get_system_admin()
        return {
            "X-User-Id": str(admin.id),
            "X-Username": quote(admin.username),
            "X-User-Scopes": " ".join(admin.scopes),
        }

    async def get_email(self, user_id: UUID) -> str | None:
        try:
            resp = await self._client.get(f"/users/{user_id}", headers=self._headers())
            if resp.status_code == 200:
                return resp.json().get("email")
        except Exception:
            pass
        return None


_users_client = UsersClient()


def get_users_client() -> UsersClient:
    return _users_client


# ---------------------------------------------------------------------------
# NotificationsClient — fire-and-forget email dispatch to notifications-ms
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_notifications_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.notifications_ms_url,
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )


class NotificationsClient:
    @property
    def _client(self) -> httpx.AsyncClient:
        return _get_notifications_http_client()

    def _headers(self) -> dict[str, str]:
        admin = _get_system_admin()
        return {
            "X-User-Id": str(admin.id),
            "X-Username": quote(admin.username),
            "X-User-Scopes": " ".join(admin.scopes),
        }

    async def send(
        self, *, to: str, notification_type: str, data: dict | None = None
    ) -> None:
        try:
            logger.debug("Sending notification from properties-ms | type={} to={} data={}", notification_type, to, data)
            await self._client.post(
                "/notifications/dispatch",
                json={
                    "notification_type": notification_type,
                    "to": to,
                    "data": data or {},
                    "triggered_by": "properties-ms",
                },
                headers=self._headers(),
            )
            logger.debug("Successfully sent notification from properties-ms | type={} to={}", notification_type, to)
        except Exception as exc:
            logger.error("Failed to send notification from properties-ms | type={} to={} error={}", notification_type, to, exc)


_notifications_client = NotificationsClient()


def get_notifications_client() -> NotificationsClient:
    return _notifications_client
