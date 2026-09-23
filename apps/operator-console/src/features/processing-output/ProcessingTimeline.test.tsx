import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { ProcessingTimeline } from "./ProcessingTimeline";

test("shows active processing before output is persisted", () => {
    render(
        <ProcessingTimeline
            run={{
                id: "run-42",
                previous_run_id: null,
                status: "RUNNING",
                queued_at: "2026-09-16T12:00:00Z",
                started_at: "2026-09-16T12:00:01Z",
                status_changed_at: "2026-09-16T12:00:01Z",
                finished_at: null,
                attempt_count: 1,
                failure: null,
                processing_output: null,
                review_resolution: null,
            }}
        />,
    );

    expect(screen.getByText("Processing progress")).toBeVisible();
    expect(screen.getByText("Extracting readable PDF text.")).toBeVisible();
    expect(screen.getAllByLabelText("In progress")).toHaveLength(6);
});

test("shows completed and skipped stages after a successful run", () => {
    render(
        <ProcessingTimeline
            run={{
                id: "run-42",
                previous_run_id: null,
                status: "COMPLETED",
                queued_at: "2026-09-16T12:00:00Z",
                started_at: "2026-09-16T12:00:01Z",
                status_changed_at: "2026-09-16T12:00:05Z",
                finished_at: "2026-09-16T12:00:05Z",
                attempt_count: 1,
                failure: null,
                processing_output: {
                    embedded_text: {
                        method: "PYMUPDF",
                        quality: "SUFFICIENT",
                        page_count: 1,
                        character_count: 150,
                        non_whitespace_character_count: 120,
                        extracted_at: "2026-09-16T12:00:02Z",
                    },
                    ocr_text: null,
                    selected_text: {
                        source: "EMBEDDED",
                        reason: "EMBEDDED_SUFFICIENT",
                        selected_at: "2026-09-16T12:00:03Z",
                    },
                    classification: {
                        document_type: "INVOICE",
                        reason: "KEYWORD_MATCHED",
                        classified_at: "2026-09-16T12:00:04Z",
                    },
                    invoice_extraction: {
                        method: "DETERMINISTIC_RULES",
                        invoice_number: "INV-42",
                        issue_date: "2026-09-16",
                        supplier_name: "Acme Ltd",
                        currency: "EUR",
                        total_amount: "12.50",
                        extracted_at: "2026-09-16T12:00:05Z",
                    },
                    invoice_validation: {
                        decision: "AUTO_APPROVE",
                        issues: [],
                        validated_at: "2026-09-16T12:00:06Z",
                    },
                },
                review_resolution: null,
            }}
        />,
    );

    expect(
        screen.getByText("Skipped because embedded text was sufficient."),
    ).toBeVisible();
    expect(screen.getByText("All implemented stages finished.")).toBeVisible();
    expect(screen.getByText("Invoice approved automatically.")).toBeVisible();
    expect(screen.getAllByLabelText("Completed")).toHaveLength(7);
});

test("shows the review handoff after an incomplete invoice", () => {
    render(
        <ProcessingTimeline
            run={{
                id: "run-42",
                previous_run_id: null,
                status: "REVIEW_REQUIRED",
                queued_at: "2026-09-16T12:00:00Z",
                started_at: "2026-09-16T12:00:01Z",
                status_changed_at: "2026-09-16T12:00:07Z",
                finished_at: null,
                attempt_count: 1,
                failure: null,
                processing_output: {
                    embedded_text: {
                        method: "PYMUPDF",
                        quality: "SUFFICIENT",
                        page_count: 1,
                        character_count: 150,
                        non_whitespace_character_count: 120,
                        extracted_at: "2026-09-16T12:00:02Z",
                    },
                    ocr_text: null,
                    selected_text: {
                        source: "EMBEDDED",
                        reason: "EMBEDDED_SUFFICIENT",
                        selected_at: "2026-09-16T12:00:03Z",
                    },
                    classification: {
                        document_type: "INVOICE",
                        reason: "KEYWORD_MATCHED",
                        classified_at: "2026-09-16T12:00:04Z",
                    },
                    invoice_extraction: {
                        method: "DETERMINISTIC_RULES",
                        invoice_number: "INV-42",
                        issue_date: null,
                        supplier_name: "Acme Ltd",
                        currency: null,
                        total_amount: null,
                        extracted_at: "2026-09-16T12:00:05Z",
                    },
                    invoice_validation: {
                        decision: "REVIEW_REQUIRED",
                        issues: ["MISSING_ISSUE_DATE"],
                        validated_at: "2026-09-16T12:00:06Z",
                    },
                },
                review_resolution: null,
            }}
        />,
    );

    expect(
        screen.getByText("Invoice requires an operator review."),
    ).toBeVisible();
    expect(
        screen.getByText("Automated processing paused for operator review."),
    ).toBeVisible();
});
