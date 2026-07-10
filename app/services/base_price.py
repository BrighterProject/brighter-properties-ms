"""Derive a property's base price from its pricing calendar.

The base ``price_per_night`` is no longer entered by owners; it is the cheapest
configured nightly rate — the "from X / night" price shown on cards. It is
recomputed whenever weekday prices or date overrides change so the stored value
always reflects the current pricing calendar.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID


async def compute_derived_base_price(property_id: UUID) -> Decimal | None:
    """Return the cheapest configured nightly price, or ``None`` if none is set.

    Considers both weekday prices and date-override prices. Returns ``None`` when
    the property has no pricing at all — there is nothing to derive from and the
    caller should leave the stored value untouched.

    Args:
        property_id: Property whose pricing calendar to inspect.

    Returns:
        The minimum configured price, or ``None`` when no pricing exists.
    """
    from app.models import PropertyDatePriceOverride, PropertyWeekdayPrice

    prices: list[Decimal] = [
        w.price for w in await PropertyWeekdayPrice.filter(property_id=property_id)
    ]
    prices += [
        o.price for o in await PropertyDatePriceOverride.filter(property_id=property_id)
    ]
    return min(prices) if prices else None


async def sync_base_price(property_id: UUID) -> Decimal | None:
    """Recompute and persist ``price_per_night`` from the pricing calendar.

    Args:
        property_id: Property to update.

    Returns:
        The derived price, or ``None`` when the property has no pricing (in which
        case the stored value is left unchanged).
    """
    from app.models import Property

    derived = await compute_derived_base_price(property_id)
    if derived is None:
        return None
    prop = await Property.get_or_none(id=property_id)
    if prop is not None and prop.price_per_night != derived:
        prop.price_per_night = derived
        await prop.save(update_fields=["price_per_night"])
    return derived
