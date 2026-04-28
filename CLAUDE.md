# CLAUDE.md — brighter-properties-ms

FastAPI microservice for managing rental properties with i18n support (part of the BrighterProject platform).

## Package management

Always use `uv`. Never use `pip` directly.

```bash
uv add <package>       # add dependency
uv sync                # install from lockfile
uv run <command>       # run in the venv
```

## Running

```bash
uv run pytest                                                     # run tests
uv run uvicorn main:application --host 0.0.0.0 --port 8001       # dev server

# Seed the DB with Bulgarian property fixtures (skips if active properties exist)
DB_URL=asyncpg://user:pass@localhost:5432/brighter uv run python scripts/seed.py
DB_URL=... uv run python scripts/seed.py --force   # re-seed even if data exists
```

## Architecture

### Technology Stack

- **API Framework**: FastAPI with Uvicorn
- **Database**: PostgreSQL with Tortoise ORM and Aerich migrations
- **Testing**: pytest with custom markers and fixtures

## Auth architecture — critical

Auth is delegated entirely to Traefik via `forwardAuth`. The JWT is validated at the gateway; this service only reads the headers Traefik injects after a successful check:

| Header          | Type   | Description                        |
|-----------------|--------|------------------------------------|
| `X-User-Id`     | UUID   | Authenticated user's ID            |
| `X-Username`    | string | Authenticated user's username      |
| `X-User-Scopes` | string | Space-separated list of scopes     |

`get_current_user()` in `app/deps.py` reads these headers — it does not validate any token itself. **Do not add JWT validation middleware inside this service.**

The service is designed to run behind Traefik. Direct calls without those headers will receive 422.

## Project structure

```
app/
  settings.py          # DB_URL, USERS_MS_URL (env vars with defaults)
  models.py            # Tortoise ORM models (Property, PropertyTranslation, PropertyImage, PropertyUnavailability)
  schemas.py           # Pydantic schemas — enums mirrored from models.py
  crud.py              # Data access layer, extends ms_core.CRUD
  deps.py              # Auth dependencies and pre-built scope checkers
  scopes.py            # PropertyScope StrEnum + PROPERTY_SCOPE_DESCRIPTIONS
  routers/
    property.py        # /properties CRUD
    translations.py    # /properties/{id}/translations
    images.py          # /properties/{id}/images
    unavail.py         # /properties/{id}/unavailabilities
    pricing.py         # /properties/{id}/pricing — weekday prices, date overrides, price resolve
tests/
  conftest.py          # Fixtures: owner_client, admin_client, anon_app, client_factory
  factories.py         # make_user(), make_admin(), property_create_payload(), etc.
  test_*.py            # One file per router + edge cases + schemas + scopes
```

## Pseudo-dynamic pricing

Models: `PropertyWeekdayPrice` (0=Mon…6=Sun), `PropertyDatePriceOverride` (date range + optional label).
Router: `app/routers/pricing.py` — prefix `/properties/{property_id}/pricing`.
Auth: public GETs; mutations require `properties:schedule` scope (owner) or `admin:properties:write` (admin).
Priority: date override › weekday › base price.
Resolution: `GET /pricing/resolve?start_date=&end_date=` returns per-night breakdown with source field (`base` | `weekday` | `date_override`).
Tested in `tests/test_pricing_router.py` and `tests/test_price_resolver.py`.

## ms-core

`ms-core` is an internal library sourced from GitHub (`HexChap/MSCore`). It provides:

- `ms_core.CRUD[Model, ResponseSchema]` — base class for all CRUD operations
- `ms_core.setup_app(app, db_url, routers_path, models)` — wires Tortoise ORM and auto-discovers all router files under `routers_path`

New router files placed in `app/routers/` are picked up automatically by `setup_app` — no manual registration needed.

## Key formats

**PropertyType** enum: `apartment` | `house` | `villa` | `hotel` | `hostel` | `guesthouse` | `room` | `other`

**PropertyStatus** enum: `active` | `inactive` | `maintenance` | `pending_approval`

**CancellationPolicy** enum: `free` | `moderate` | `strict`

**Supported locales**: `en`, `bg`, `ru` (defined in `models.SUPPORTED_LOCALES`)

**AmenityType** enum (stored as JSON list on Property):
`wifi` | `air_conditioning` | `kitchen` | `washing_machine` | `fireplace` | `bbq` | `mountain_view` | `ski_storage` | `breakfast_included` | `reception_24h` | `sea_view` | `balcony` | `pool` | `garden` | `pet_friendly` | `coffee_machine`

## i18n — PropertyTranslation

Translatable fields (`name`, `description`, `address`, `house_rules`) live in a separate `PropertyTranslation` table with a `(property_id, locale)` unique constraint.

Translatable fields: `name`, `description`, `address`, `house_rules` (optional). `house_rules` can be null; the others are required on creation.

- `POST /properties` requires at least one translation in the `translations` list; the `bg` locale is mandatory.
- `GET /properties/` and `GET /properties/bulk` accept a `?lang=` query param (default `bg`). The CRUD layer resolves the name with fallback: requested locale → `bg` → first available.
- `GET /properties/{id}` returns all translations in the response.
- Translations are managed via `/properties/{id}/translations` (CRUD by locale).

## Cache headers

`GET /properties/` — `Cache-Control: public, max-age=30`
`GET /properties/{id}` — `Cache-Control: public, max-age=60`

Set in the router. Downstream caches (Traefik/browser) serve stale data within the TTL — keep this in mind when testing updates.

## Adding a new resource

1. Add Tortoise model to `app/models.py`
2. Add Pydantic schemas to `app/schemas.py` (mirror any new enums from models)
3. Create a CRUD class in `app/crud.py` extending `ms_core.CRUD`
4. Create `app/routers/<resource>.py` — auto-discovered, no extra wiring
5. Add relevant scopes to `app/scopes.py` following the `resource:action` / `admin:resource:action` pattern
6. Wire scope deps in `app/deps.py`

## Authorization patterns

Use the pre-built dependencies from `app/deps.py`:

```python
# Owner only
Depends(can_write_property)

# Owner or admin (preferred for mutating operations)
Depends(can_write_or_admin)

# Admin only
Depends(can_admin_write)

# Custom scopes
Depends(require_scopes(PropertyScope.READ, PropertyScope.ME))
```

`_owner_or_admin()` passes if the user has the owner-level scope OR the admin-level scope OR the top-level `admin:properties` scope.

`is_admin` on `CurrentUser` checks for `admin:scopes` (the global admin scope, not property-specific).

## Testing conventions

- **Mock the CRUD layer**, not the database. Use `unittest.mock.AsyncMock`.
- Use `owner_client` / `admin_client` fixtures for most tests.
- Use `anon_app` when you need the real auth/scope deps to run (401/403 assertions).
- Use `client_factory(make_user(scopes=[...]))` for custom scope combinations.
- Build test data with factories from `tests/factories.py`, not inline dicts.

```python
from unittest.mock import AsyncMock, patch

def test_create_property(owner_client):
    payload = property_create_payload()
    with patch("app.routers.property.property_crud") as mock_crud:
        mock_crud.create_property = AsyncMock(return_value=property_response())
        resp = owner_client.post("/properties", json=payload)
    assert resp.status_code == 201
```

## Database

- Development/tests: SQLite in-memory (`sqlite://:memory:`, default)
- Production: PostgreSQL (`DB_URL` env var)
- Migrations: Aerich — config in `pyproject.toml`, stored in `./migrations/`

```bash
uv run aerich migrate --name <description>   # generate migration
uv run aerich upgrade                        # apply migrations
```

## Environment variables

| Variable       | Default                  | Description                        |
|----------------|--------------------------|------------------------------------|
| `DB_URL`       | `sqlite://:memory:`      | Database connection string         |
| `USERS_MS_URL` | `http://localhost:8000`  | Users microservice base URL        |
