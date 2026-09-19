"""Exact-match evaluation for synthetic invoice-extraction corpora."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

type InvoiceFieldName = Literal[
    "invoice_number",
    "issue_date",
    "supplier_name",
    "currency",
    "total_amount",
]

INVOICE_FIELDS: tuple[InvoiceFieldName, ...] = (
    "invoice_number",
    "issue_date",
    "supplier_name",
    "currency",
    "total_amount",
)


class InvalidEvaluationCorpus(ValueError):
    """Raised when a synthetic evaluation corpus does not meet its schema."""


@dataclass(frozen=True, slots=True)
class InvoiceFields:
    invoice_number: str | None
    issue_date: str | None
    supplier_name: str | None
    currency: str | None
    total_amount: str | None

    def value_for(self, field: InvoiceFieldName) -> str | None:
        return getattr(self, field)

    def as_dict(self) -> dict[InvoiceFieldName, str | None]:
        return {field: self.value_for(field) for field in INVOICE_FIELDS}


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    text: str
    expected: InvoiceFields


@dataclass(frozen=True, slots=True)
class EvaluationCorpus:
    dataset_id: str
    schema_version: int
    cases: tuple[EvaluationCase, ...]


@dataclass(frozen=True, slots=True)
class FieldEvaluation:
    field: InvoiceFieldName
    exact_matches: int
    total_cases: int

    @property
    def exact_match_rate(self) -> float:
        return self.exact_matches / self.total_cases if self.total_cases else 0.0


@dataclass(frozen=True, slots=True)
class InvoiceExtractionMismatch:
    case_id: str
    field: InvoiceFieldName
    expected: str | None
    actual: str | None


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    dataset_id: str
    schema_version: int
    total_cases: int
    exact_case_matches: int
    field_evaluations: tuple[FieldEvaluation, ...]
    mismatches: tuple[InvoiceExtractionMismatch, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "schema_version": self.schema_version,
            "total_cases": self.total_cases,
            "exact_case_matches": self.exact_case_matches,
            "exact_case_match_rate": _rate(self.exact_case_matches, self.total_cases),
            "fields": {
                evaluation.field: {
                    "exact_matches": evaluation.exact_matches,
                    "total_cases": evaluation.total_cases,
                    "exact_match_rate": _rate(
                        evaluation.exact_matches,
                        evaluation.total_cases,
                    ),
                }
                for evaluation in self.field_evaluations
            },
            "mismatches": [
                {
                    "case_id": mismatch.case_id,
                    "field": mismatch.field,
                    "expected": mismatch.expected,
                    "actual": mismatch.actual,
                }
                for mismatch in self.mismatches
            ],
        }


class InvoiceExtractionEvaluator:
    """Evaluate a text-to-fields callable against a versioned corpus."""

    def evaluate(
        self,
        *,
        corpus: EvaluationCorpus,
        extractor: Callable[[str], InvoiceFields],
    ) -> EvaluationReport:
        matches_by_field = {field: 0 for field in INVOICE_FIELDS}
        exact_case_matches = 0
        mismatches: list[InvoiceExtractionMismatch] = []
        for case in corpus.cases:
            actual = extractor(case.text)
            case_matches = True
            for field in INVOICE_FIELDS:
                expected_value = case.expected.value_for(field)
                actual_value = actual.value_for(field)
                if actual_value == expected_value:
                    matches_by_field[field] += 1
                    continue
                case_matches = False
                mismatches.append(
                    InvoiceExtractionMismatch(
                        case_id=case.id,
                        field=field,
                        expected=expected_value,
                        actual=actual_value,
                    )
                )
            if case_matches:
                exact_case_matches += 1

        return EvaluationReport(
            dataset_id=corpus.dataset_id,
            schema_version=corpus.schema_version,
            total_cases=len(corpus.cases),
            exact_case_matches=exact_case_matches,
            field_evaluations=tuple(
                FieldEvaluation(
                    field=field,
                    exact_matches=matches_by_field[field],
                    total_cases=len(corpus.cases),
                )
                for field in INVOICE_FIELDS
            ),
            mismatches=tuple(mismatches),
        )


def load_invoice_extraction_corpus(path: Path) -> EvaluationCorpus:
    try:
        raw_corpus: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InvalidEvaluationCorpus(f"unable to load corpus: {path}") from error
    corpus = _require_mapping(raw_corpus, "corpus")
    dataset_id = _require_non_blank_string(corpus.get("dataset_id"), "dataset_id")
    schema_version = corpus.get("schema_version")
    if type(schema_version) is not int or schema_version < 1:
        raise InvalidEvaluationCorpus("schema_version must be a positive integer")
    raw_cases = _require_non_empty_list(corpus.get("cases"), "cases")
    cases = tuple(_to_case(raw_case) for raw_case in raw_cases)
    if len({case.id for case in cases}) != len(cases):
        raise InvalidEvaluationCorpus("case ids must be unique")
    return EvaluationCorpus(
        dataset_id=dataset_id,
        schema_version=schema_version,
        cases=cases,
    )


def _to_case(raw_case: object) -> EvaluationCase:
    case = _require_mapping(raw_case, "case")
    return EvaluationCase(
        id=_require_non_blank_string(case.get("id"), "case.id"),
        text=_require_string(case.get("text"), "case.text"),
        expected=_to_invoice_fields(case.get("expected")),
    )


def _to_invoice_fields(raw_fields: object) -> InvoiceFields:
    fields = _require_mapping(raw_fields, "case.expected")
    unexpected_fields = set(fields) - set(INVOICE_FIELDS)
    missing_fields = set(INVOICE_FIELDS) - set(fields)
    if unexpected_fields or missing_fields:
        raise InvalidEvaluationCorpus("case.expected must contain exactly the invoice fields")
    return InvoiceFields(
        invoice_number=_require_nullable_string(fields["invoice_number"], "invoice_number"),
        issue_date=_require_nullable_string(fields["issue_date"], "issue_date"),
        supplier_name=_require_nullable_string(fields["supplier_name"], "supplier_name"),
        currency=_require_nullable_string(fields["currency"], "currency"),
        total_amount=_require_nullable_string(fields["total_amount"], "total_amount"),
    )


def _require_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidEvaluationCorpus(f"{field} must be an object")
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        raise InvalidEvaluationCorpus(f"{field} must be an object")
    return cast(dict[str, object], mapping)


def _require_non_empty_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list) or not value:
        raise InvalidEvaluationCorpus(f"{field} must be a non-empty array")
    return cast(list[object], value)


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise InvalidEvaluationCorpus(f"{field} must be a string")
    return value


def _require_non_blank_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidEvaluationCorpus(f"{field} must be a non-blank string")
    return value


def _require_nullable_string(value: object, field: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise InvalidEvaluationCorpus(f"case.expected.{field} must be a string or null")


def _rate(matches: int, total: int) -> float:
    return round(matches / total, 4) if total else 0.0
