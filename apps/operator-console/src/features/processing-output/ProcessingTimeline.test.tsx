import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";

import { type DocumentStatus } from "../../api/documentApi";
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
                ai_proposal: null,
                ai_proposal_failure: null,
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
                ai_proposal: null,
                ai_proposal_failure: null,
            }}
        />,
    );

    expect(
        screen.getByText("Skipped because embedded text was sufficient."),
    ).toBeVisible();
    expect(
        screen.getByText("Deterministic processing finished."),
    ).toBeVisible();
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
                ai_proposal: null,
                ai_proposal_failure: null,
            }}
        />,
    );

    expect(
        screen.getByText("Invoice requires an operator review."),
    ).toBeVisible();
    expect(
        screen.getByText(
            "Deterministic processing finished; operator review is required.",
        ),
    ).toBeVisible();
});

type ProcessingRun = DocumentStatus["current_run"];
const invoiceRun: ProcessingRun = {
    id: "run-42",
    previous_run_id: null,
    status: "REVIEW_REQUIRED",
    queued_at: "2026-09-29T12:00:00Z",
    started_at: "2026-09-29T12:00:01Z",
    status_changed_at: "2026-09-29T12:00:05Z",
    finished_at: null,
    attempt_count: 1,
    failure: null,
    review_resolution: null,
    ai_proposal: null,
    ai_proposal_failure: null,
    processing_output: {
        embedded_text: null,
        ocr_text: null,
        selected_text: null,
        classification: {
            document_type: "INVOICE",
            reason: "KEYWORD_MATCHED",
            classified_at: "2026-09-29T12:00:04Z",
        },
        invoice_extraction: null,
        invoice_validation: null,
    },
};

test.each([
    ["DISABLED", "Skipped", "AI proposals are disabled for this run."],
    [
        "RUNNING",
        "In progress",
        "AI proposal pending; document outcome unchanged.",
    ],
    [
        "COMPLETED",
        "Completed",
        "AI execution completed; proposal validity and document approval are separate.",
    ],
    ["FAILED", "Failed", "AI proposal failed; document outcome unchanged."],
] as const)(
    "renders recorded AI %s independently of review handoff",
    (status, icon, detail) => {
        const at = new Date().toISOString();
        render(
            <ProcessingTimeline
                run={{
                    ...invoiceRun,
                    ai_execution: {
                        status,
                        started_at: status === "DISABLED" ? null : at,
                        finished_at: status === "RUNNING" ? null : at,
                        status_changed_at: at,
                    },
                }}
            />,
        );
        const stages = screen.getAllByRole("listitem");
        const aiStage = stages.at(-1)!;
        expect(within(aiStage).getByText("Advisory AI proposal")).toBeVisible();
        expect(within(aiStage).getByLabelText(icon)).toBeVisible();
        expect(within(aiStage).getByText(detail)).toBeVisible();
        expect(
            within(stages.at(-2)!).getByText("Review handoff"),
        ).toBeVisible();
    },
);

test("does not animate a stale running AI marker as live progress", () => {
    render(
        <ProcessingTimeline
            run={{
                ...invoiceRun,
                ai_execution: {
                    status: "RUNNING",
                    started_at: "2026-09-16T12:00:04Z",
                    finished_at: null,
                    status_changed_at: "2026-09-16T12:00:04Z",
                },
            }}
        />,
    );
    const aiStage = screen.getAllByRole("listitem").at(-1)!;
    expect(within(aiStage).getByLabelText("Pending")).toBeVisible();
    expect(
        within(aiStage).getByText(
            "AI execution still reports running; automatic updates are paused.",
        ),
    ).toBeVisible();
});

test("does not infer disabled AI from a missing execution record", () => {
    render(<ProcessingTimeline run={{ ...invoiceRun, ai_execution: null }} />);
    expect(
        screen.getByText("AI execution state is not recorded."),
    ).toBeVisible();
    expect(
        screen.queryByText("AI proposals are disabled for this run."),
    ).not.toBeInTheDocument();
});

test("preserves legacy failure evidence without inventing an execution state", () => {
    render(
        <ProcessingTimeline
            run={{
                ...invoiceRun,
                ai_proposal_failure: {
                    provider: "OLLAMA",
                    model_reference: "qwen3:8b",
                    code: "TIMEOUT",
                    failed_at: "2026-09-29T12:00:06Z",
                },
            }}
        />,
    );
    expect(
        screen.getByText(
            "AI outcome recorded; execution state is not recorded.",
        ),
    ).toBeVisible();
});

test("skips advisory AI for a classified non-invoice", () => {
    render(
        <ProcessingTimeline
            run={{
                ...invoiceRun,
                processing_output: {
                    ...invoiceRun.processing_output!,
                    classification: {
                        document_type: "UNKNOWN",
                        reason: "NO_MATCH",
                        classified_at: "2026-09-29T12:00:04Z",
                    },
                },
            }}
        />,
    );
    expect(
        screen.getByText(
            "AI proposals are not applicable to this document type.",
        ),
    ).toBeVisible();
});
