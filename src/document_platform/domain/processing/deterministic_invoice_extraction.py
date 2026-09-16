"""Conservative, deterministic extraction for labelled invoice fields."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from document_platform.domain.processing.invoice_extraction import (
    InvoiceExtraction,
    InvoiceExtractionMethod,
)


class DeterministicInvoiceExtractionPolicy:
    """Extract only fields introduced by an explicit supported label."""

    _INVOICE_NUMBER_PATTERNS = (
        re.compile(
            r"^\s*(?:invoice\s*(?:number|no\.?|#)|fattura\s*(?:numero|n\.?))\s*[:#-]?\s*(.+?)\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
    )
    _SUPPLIER_PATTERNS = (
        re.compile(
            r"^\s*(?:supplier|fornitore)\s*:\s*(.+?)\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
    )
    _DATE_PATTERNS = (
        re.compile(
            r"^\s*(?:invoice\s+date|date|data)\s*:\s*(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
    )
    _TOTAL_PATTERN = re.compile(
        r"^\s*(?:total(?:\s+amount)?|totale(?:\s+importo)?)\s*[:#-]?\s*"
        r"(?:(EUR|USD|GBP)\s*)?([€$£]?)\s*([0-9][0-9., ]*)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    _CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP"}

    def extract(
        self,
        *,
        processing_run_id: UUID,
        text: str,
        extracted_at: datetime,
    ) -> InvoiceExtraction:
        currency, total_amount = self._extract_total(text)
        return InvoiceExtraction(
            processing_run_id=processing_run_id,
            method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
            invoice_number=self._extract_labelled_value(self._INVOICE_NUMBER_PATTERNS, text),
            issue_date=self._extract_date(text),
            supplier_name=self._extract_labelled_value(self._SUPPLIER_PATTERNS, text),
            currency=currency,
            total_amount=total_amount,
            extracted_at=extracted_at,
        )

    def _extract_total(self, text: str) -> tuple[str | None, Decimal | None]:
        match = self._TOTAL_PATTERN.search(text)
        if match is None:
            return None, None
        currency_code, currency_symbol, raw_amount = match.groups()
        amount = _parse_decimal(raw_amount)
        if amount is None:
            return None, None
        currency = (
            currency_code.upper() if currency_code else self._CURRENCY_SYMBOLS.get(currency_symbol)
        )
        return currency, amount

    @staticmethod
    def _extract_labelled_value(patterns: tuple[re.Pattern[str], ...], text: str) -> str | None:
        for pattern in patterns:
            match = pattern.search(text)
            if match is not None:
                return match.group(1).strip() or None
        return None

    def _extract_date(self, text: str) -> date | None:
        raw_value = self._extract_labelled_value(self._DATE_PATTERNS, text)
        if raw_value is None:
            return None
        for format_string in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw_value, format_string).date()
            except ValueError:
                continue
        return None


def _parse_decimal(raw_value: str) -> Decimal | None:
    compact = raw_value.replace(" ", "")
    if "." in compact and "," in compact:
        decimal_separator = max(compact.rfind("."), compact.rfind(","))
        integer_part = re.sub(r"[.,]", "", compact[:decimal_separator])
        compact = f"{integer_part}.{compact[decimal_separator + 1 :]}"
    elif "," in compact:
        compact = compact.replace(",", ".")
    try:
        return Decimal(compact)
    except InvalidOperation:
        return None
