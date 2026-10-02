import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { ProcessingOutputPanel } from "./ProcessingOutputPanel";

test("shows a waiting state before processing creates output", () => {
    render(<ProcessingOutputPanel output={null} />);

    expect(screen.getByText("Processing results")).toBeVisible();
    expect(
        screen.getByText("Waiting for the first processing result."),
    ).toBeVisible();
});

test("shows safe processing metadata without extracted text", () => {
    render(
        <ProcessingOutputPanel
            output={{
                embedded_text: {
                    method: "PYMUPDF",
                    quality: "OCR_RECOMMENDED",
                    page_count: 2,
                    character_count: 10,
                    non_whitespace_character_count: 9,
                    extracted_at: "2026-09-16T12:00:00Z",
                },
                ocr_text: {
                    method: "TESSERACT",
                    page_count: 2,
                    character_count: 22,
                    non_whitespace_character_count: 19,
                    extracted_at: "2026-09-16T12:00:01Z",
                },
                selected_text: {
                    source: "OCR",
                    reason: "OCR_HAS_MORE_TEXT",
                    selected_at: "2026-09-16T12:00:02Z",
                },
                classification: {
                    document_type: "INVOICE",
                    reason: "KEYWORD_MATCHED",
                    classified_at: "2026-09-16T12:00:03Z",
                },
                invoice_extraction: {
                    method: "DETERMINISTIC_RULES",
                    invoice_number: "INV-42",
                    issue_date: "2026-09-16",
                    supplier_name: "Acme Ltd",
                    currency: "EUR",
                    total_amount: "12.50",
                    extracted_at: "2026-09-16T12:00:04Z",
                },
                invoice_validation: {
                    decision: "AUTO_APPROVE",
                    issues: [],
                    validated_at: "2026-09-16T12:00:05Z",
                },
            }}
        />,
    );

    expect(screen.getByText("PyMuPDF · OCR recommended")).toBeVisible();
    expect(screen.getByText("Tesseract · 22 characters")).toBeVisible();
    expect(screen.getByText("OCR has more text")).toBeVisible();
    expect(screen.getByText("Invoice")).toBeVisible();
    expect(screen.getByText("INV-42")).toBeVisible();
    expect(screen.getByText("EUR 12.50")).toBeVisible();
    expect(screen.getByText("Auto Approve")).toBeVisible();
    expect(screen.getByText("No review required")).toBeVisible();
    expect(
        screen.queryByText("Invoice 42 Total 12.50"),
    ).not.toBeInTheDocument();
});

test("shows invoice review reasons without exposing source text", () => {
    render(
        <ProcessingOutputPanel
            output={{
                embedded_text: null,
                ocr_text: null,
                selected_text: null,
                classification: {
                    document_type: "INVOICE",
                    reason: "KEYWORD_MATCHED",
                    classified_at: "2026-09-16T12:00:03Z",
                },
                invoice_extraction: {
                    method: "DETERMINISTIC_RULES",
                    invoice_number: "INV-42",
                    issue_date: null,
                    supplier_name: "Acme Ltd",
                    currency: null,
                    total_amount: null,
                    extracted_at: "2026-09-16T12:00:04Z",
                },
                invoice_validation: {
                    decision: "REVIEW_REQUIRED",
                    issues: ["MISSING_ISSUE_DATE", "MISSING_TOTAL_AMOUNT"],
                    validated_at: "2026-09-16T12:00:05Z",
                },
            }}
        />,
    );

    expect(screen.getByText("Original extraction validation")).toBeVisible();
    expect(screen.getByText("Review Required")).toBeVisible();
    expect(
        screen.getByText("Missing Issue Date, Missing Total Amount"),
    ).toBeVisible();
    expect(screen.getAllByText("Not found")).toHaveLength(3);
});

test("marks invoice-only output as not applicable for other document types", () => {
    render(
        <ProcessingOutputPanel
            output={{
                embedded_text: null,
                ocr_text: null,
                selected_text: null,
                classification: {
                    document_type: "PURCHASE_ORDER",
                    reason: "KEYWORD_MATCHED",
                    classified_at: "2026-09-16T12:00:03Z",
                },
                invoice_extraction: null,
                invoice_validation: null,
            }}
        />,
    );

    expect(screen.getAllByText("Not applicable")).toHaveLength(2);
});

test("shows review-corrected invoice values without replacing extracted values", () => {
    render(
        <ProcessingOutputPanel
            corrections={[
                {
                    field: "SUPPLIER_NAME",
                    corrected_value: "Acme Europe Ltd",
                    source: "MANUAL",
                    corrected_at: "2026-09-16T12:00:06Z",
                },
                {
                    field: "TOTAL_AMOUNT",
                    corrected_value: "15.00",
                    source: "MANUAL",
                    corrected_at: "2026-09-16T12:00:06Z",
                },
            ]}
            output={{
                embedded_text: null,
                ocr_text: null,
                selected_text: null,
                classification: {
                    document_type: "INVOICE",
                    reason: "KEYWORD_MATCHED",
                    classified_at: "2026-09-16T12:00:03Z",
                },
                invoice_extraction: {
                    method: "DETERMINISTIC_RULES",
                    invoice_number: "INV-42",
                    issue_date: "2026-09-16",
                    supplier_name: "Acme Ltd",
                    currency: "EUR",
                    total_amount: "12.50",
                    extracted_at: "2026-09-16T12:00:04Z",
                },
                invoice_validation: null,
            }}
        />,
    );

    expect(screen.getByText("Effective invoice values")).toBeVisible();
    expect(screen.getByText("Acme Europe Ltd")).toBeVisible();
    expect(screen.getByText("EUR 15.00")).toBeVisible();
    expect(screen.getAllByText("Corrected")).toHaveLength(2);
    expect(screen.getByText("Extracted: Acme Ltd")).toBeVisible();
    expect(screen.getByText("Extracted: EUR 12.50")).toBeVisible();
});
