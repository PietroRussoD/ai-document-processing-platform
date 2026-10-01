"""Currency-code format tests."""

import pytest

from document_platform.domain.processing.currency_code import is_iso_currency_code


@pytest.mark.parametrize("value", ["CAD", "EUR"])
def test_accepts_iso_4217_alpha_codes(value: str) -> None:
    assert is_iso_currency_code(value)


@pytest.mark.parametrize("value", ["ZZZ", "eur", "EU", "EURO", "EÜR", "1UR"])
def test_rejects_values_outside_the_iso_4217_registry(value: str) -> None:
    assert not is_iso_currency_code(value)
