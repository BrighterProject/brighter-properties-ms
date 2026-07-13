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
    pricing.py         # /properties/{id}/pricing — per-date prices, resolve, coverage
tests/
  conftest.py          # Fixtures: owner_client, admin_client, anon_app, client_factory
  factories.py         # make_user(), make_admin(), property_create_payload(), etc.
  test_*.py            # One file per router + edge cases + schemas + scopes
```

## Pricing — per-date calendar (no weekday rules, no base price)

Owners price the calendar **day by day**. The calendar is the sole source of
price and availability: a date with a `PropertyDatePrice` row is bookable at that
price; a date with no row is unpriced and therefore unavailable. There are no
recurring weekday defaults and no base-price fallback. `Property.price_per_night`
was removed (migration `0005`) in favour of two **system-owned** projections,
never owner input, maintained by `app/services/pricing_cache.py`:

- `price_from` — cheapest **priced night within the `[today, today + BOOKING_WINDOW_DAYS)` horizon** (nullable; the "from X" price). Past/beyond-horizon rows don't count.
- `has_valid_pricing` — `>=1` priced night within that same horizon; gates public
  listing visibility (public `GET /properties` hides properties where it is false;
  owner-scoped `?owner_id=` listings still show unpriced drafts).

`sync_pricing_cache(property_id)` refreshes both on every calendar write.
`scripts/recompute_pricing_cache.py` (nightly cron) corrects horizon drift as
priced nights age out of / into the window.

Model: `PropertyDatePrice` (`property_id`, `date`, `price`; unique on `(property, date)`) — migration `0006` dropped `property_weekday_prices` + `property_date_price_overrides` (no back-fill).
Router: `app/routers/pricing.py` — prefix `/properties/{property_id}/pricing`.
Auth: public GETs; mutations require `properties:schedule` scope (owner) or `admin:properties:write` (admin).
Editing (both map to per-date rows):
- `GET /pricing/dates?from_date=&to_date=` — list priced nights.
- `PUT /pricing/dates` `{start_date, end_date, price}` — upsert every night in the inclusive range to one price (`start_date == end_date` sets a single day). One request per range edit.
- `DELETE /pricing/dates?start_date=&end_date=` — clear the inclusive range; those nights become unpriced/unavailable.
Resolution: `GET /pricing/resolve?start_date=&end_date=` returns the per-night breakdown (source `date`), or **409** with `unpriced_dates` when any night is unpriced. Contract unchanged, so bookings-ms needs no change.
Coverage: `GET /pricing/coverage?start=&end=` returns `unpriced_windows` (`[start_date, end_date)`, end-exclusive) — used by the frontend date picker to disable unbookable days (`app/services/coverage.py`). `GET /properties/{id}/unavailabilities` returns **real owner blocks only**.
Search: `GET /properties/?available_from=&available_to=` (`PropertyCRUD.list_properties`, `app/crud.py`) excludes properties with an overlapping owner `PropertyUnavailability` row or a confirmed booking, **and** requires every night in the requested range to be priced — it calls `compute_stay_totals()` on the candidate ids before pagination and drops any property omitted from that result (a stay with even one unpriced night, e.g. two disjoint priced ranges that don't fully cover the search, is excluded). There is no synthesized "price-gap" `PropertyUnavailability` row; unpriced-night exclusion happens only via this `compute_stay_totals()` check in search and the 409 in `GET /pricing/resolve` at booking time.
Filters v2 (BTR-51): `list_properties` returns `(items, total)` and the router surfaces the pre-pagination match count as an `X-Total-Count` header (body stays a bare list). `order_by` accepts `recommended` (default; FTS rank when `q` is set) / `price_asc` / `price_desc` / `rating_desc` — price sorts coalesce NULL `price_from` last. **With a date range**, `min_price`/`max_price` and `price_*` sorts operate on the resolved per-stay *average nightly rate* (`compute_stay_totals` total ÷ nights), not `price_from`; without dates they use `price_from` as before.
Tested in `tests/test_pricing_router.py`, `tests/test_price_resolver.py`, `tests/test_coverage.py`, `tests/test_pricing_cache.py`, `tests/test_search_pricing_coverage.py`, `tests/test_listing_filters.py`.

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
- Migrations: native tortoise CLI — config in `pyproject.toml` (`[tool.tortoise]`), stored in `./migrations/models/`

```bash
uv run tortoise -c main.TORTOISE_ORM makemigrations
uv run tortoise -c main.TORTOISE_ORM migrate
```

## Environment variables

| Variable       | Default                  | Description                        |
|----------------|--------------------------|------------------------------------|
| `DB_URL`       | `sqlite://:memory:`      | Database connection string         |
| `USERS_MS_URL` | `http://localhost:8000`  | Users microservice base URL        |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | OTLP gRPC endpoint |
| `OTEL_SDK_DISABLED` | `false` | Set `true` to skip telemetry (CI / light dev) |
| `LOG_COLORIZE` | `false` | Set `true` for ANSI-coloured logs in compose |
