from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import (
    PropertyCreate,
    PropertyFilters,
    PropertyUnavailabilityCreate,
    TranslationCreate,
)

from .factories import LATER, NOW, translation_dict


class TestPropertyCreateSchema:
    def test_valid_payload(self):
        data = PropertyCreate(
            city="Sofia",
            price_per_night=Decimal("50.00"),
            room_details="Entire apartment • 1 bathroom",
            bed_info="2 beds",
            translations=[TranslationCreate(**translation_dict("bg"))],
        )
        assert data.currency == "EUR"
        assert data.max_guests == 1
        assert data.bedrooms == 1

    def test_currency_uppercased(self):
        data = PropertyCreate(
            city="City",
            price_per_night=Decimal("10"),
            currency="eur",
            room_details="Entire apartment • 1 bathroom",
            bed_info="1 bed",
            translations=[TranslationCreate(**translation_dict("bg"))],
        )
        assert data.currency == "EUR"

    def test_negative_price_raises(self):
        with pytest.raises(ValidationError):
            PropertyCreate(
                city="City",
                price_per_night=Decimal("-5"),
                translations=[TranslationCreate(**translation_dict("bg"))],
            )

    def test_max_guests_zero_raises(self):
        with pytest.raises(ValidationError):
            PropertyCreate(
                city="City",
                price_per_night=Decimal("10"),
                max_guests=0,
                translations=[TranslationCreate(**translation_dict("bg"))],
            )

    def test_min_nights_greater_than_max_raises(self):
        with pytest.raises(ValidationError, match="min_nights"):
            PropertyCreate(
                city="City",
                price_per_night=Decimal("10"),
                room_details="Entire apartment • 1 bathroom",
                bed_info="1 bed",
                min_nights=10,
                max_nights=3,
                translations=[TranslationCreate(**translation_dict("bg"))],
            )

    def test_missing_translations_raises(self):
        with pytest.raises(ValidationError):
            PropertyCreate(
                city="City",
                price_per_night=Decimal("10"),
                translations=[],
            )

    def test_duplicate_locales_raises(self):
        with pytest.raises(ValidationError, match="Duplicate locales"):
            PropertyCreate(
                city="City",
                price_per_night=Decimal("10"),
                translations=[
                    TranslationCreate(**translation_dict("bg")),
                    TranslationCreate(**translation_dict("bg")),
                ],
            )

    def test_missing_bg_locale_raises(self):
        with pytest.raises(ValidationError, match="Bulgarian"):
            PropertyCreate(
                city="City",
                price_per_night=Decimal("10"),
                translations=[TranslationCreate(**translation_dict("en"))],
            )

    def test_multiple_locales_accepted(self):
        data = PropertyCreate(
            city="Sofia",
            price_per_night=Decimal("50.00"),
            room_details="Entire apartment • 1 bathroom",
            bed_info="2 beds",
            translations=[
                TranslationCreate(**translation_dict("bg")),
                TranslationCreate(**translation_dict("en")),
            ],
        )
        assert len(data.translations) == 2


class TestTranslationSchema:
    def test_valid_translation(self):
        tr = TranslationCreate(**translation_dict("bg"))
        assert tr.locale == "bg"

    def test_unsupported_locale_raises(self):
        with pytest.raises(ValidationError, match="Unsupported locale"):
            data = translation_dict("bg")
            data["locale"] = "fr"
            TranslationCreate(**data)

    def test_name_too_short_raises(self):
        with pytest.raises(ValidationError):
            TranslationCreate(**translation_dict("bg", name="X"))

    def test_description_too_short_raises(self):
        with pytest.raises(ValidationError):
            TranslationCreate(**translation_dict("bg", description="Short"))


class TestPropertyFiltersSchema:
    def test_price_range_inversion_raises(self):
        with pytest.raises(Exception, match="min_price"):
            PropertyFilters(min_price=Decimal("100"), max_price=Decimal("10"))

    def test_defaults(self):
        f = PropertyFilters()
        assert f.page == 1
        assert f.page_size == 20
        assert f.status is None

    def test_page_size_capped(self):
        with pytest.raises(ValidationError):
            PropertyFilters(page_size=999)


class TestUnavailabilitySchema:
    def test_end_before_start_raises(self):
        with pytest.raises(Exception, match="end_datetime"):
            PropertyUnavailabilityCreate(
                start_datetime=LATER,
                end_datetime=NOW,
            )

    def test_valid_window(self):
        obj = PropertyUnavailabilityCreate(
            start_datetime=NOW,
            end_datetime=LATER,
            reason="Holiday",
        )
        assert obj.reason == "Holiday"
