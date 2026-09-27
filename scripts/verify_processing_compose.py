"""Smoke-test the running local processing Compose profile through its console."""

import argparse
import time
from uuid import UUID, uuid4

import httpx
import pymupdf


class SmokeTestError(Exception):
    """A running local stack did not complete the expected processing path."""


def synthetic_invoice_pdf() -> bytes:
    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text(
            (72, 72),
            (
                "INVOICE\n"
                "Supplier: Example Ltd\n"
                "Customer: Demo Corp\n"
                "Invoice date: 2026-09-24\n"
                "Total amount: EUR 100.00\n"
                "Synthetic document for local Compose verification only.\n"
            )
            * 2,
        )
        return document.tobytes()
    finally:
        document.close()


def document_console_url(base_url: str, document_id: UUID) -> str:
    return str(
        httpx.URL(base_url).copy_with(path="/").copy_add_param("documentId", str(document_id))
    )


def verify_processing(
    client: httpx.Client,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float = 1.0,
) -> UUID:
    page = client.get("/")
    page.raise_for_status()
    if "Document Processing Console" not in page.text:
        raise SmokeTestError("The console did not return its application page")

    upload = client.post(
        "/api/v1/documents",
        headers={"Idempotency-Key": f"compose-smoke-{uuid4()}"},
        files={"document": ("compose-smoke.pdf", synthetic_invoice_pdf(), "application/pdf")},
    )
    upload.raise_for_status()
    if upload.status_code != 202:
        raise SmokeTestError(f"Upload returned {upload.status_code}, expected 202")
    document_id = UUID(upload.json()["document_id"])

    deadline = time.monotonic() + timeout_seconds
    while True:
        response = client.get(f"/api/v1/documents/{document_id}")
        response.raise_for_status()
        document = response.json()
        status = document["status"]
        if status == "REVIEW_REQUIRED":
            current_run = document["current_run"]
            output = current_run["processing_output"]
            if (
                current_run["status"] != "REVIEW_REQUIRED"
                or output["embedded_text"] is None
                or output["classification"]["document_type"] != "INVOICE"
            ):
                raise SmokeTestError("Review status lacks the expected processing evidence")
            return document_id
        if status in {"APPROVED", "REJECTED", "FAILED"}:
            raise SmokeTestError(f"Document reached unexpected terminal status {status}")
        if time.monotonic() >= deadline:
            raise SmokeTestError(f"Document {document_id} stayed in {status} past the timeout")
        time.sleep(poll_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")

    try:
        with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
            document_id = verify_processing(client, timeout_seconds=args.timeout_seconds)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, SmokeTestError) as error:
        raise SystemExit(f"Compose smoke test failed: {error}") from error
    print(f"Compose smoke test passed: document {document_id} reached REVIEW_REQUIRED")
    print(f"Console document: {document_console_url(args.base_url, document_id)}")


if __name__ == "__main__":
    main()
