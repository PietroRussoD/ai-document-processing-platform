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
            }}
        />,
    );

    expect(screen.getByText("PyMuPDF · OCR recommended")).toBeVisible();
    expect(screen.getByText("Tesseract · 22 characters")).toBeVisible();
    expect(screen.getByText("OCR has more text")).toBeVisible();
    expect(screen.getByText("Invoice")).toBeVisible();
    expect(screen.getByText("INV-42")).toBeVisible();
    expect(screen.getByText("EUR 12.50")).toBeVisible();
    expect(
        screen.queryByText("Invoice 42 Total 12.50"),
    ).not.toBeInTheDocument();
});
