"""ISO 4217 alpha-code validation for invoice processing."""

from iso4217 import Currency


def is_iso_currency_code(value: str) -> bool:
    try:
        Currency(value)
    except ValueError:
        return False
    return True
