import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { type PropsWithChildren } from "react";
import { expect, test, vi } from "vitest";

import { type DocumentStatus } from "../../api/documentApi";
import { DocumentStatusPanel } from "./DocumentStatusPanel";
import { statusPollInterval } from "./statusPolling";

const DOCUMENT_ID = "11111111-1111-4111-8111-111111111111";

test.each([
    ["UPLOADED", "QUEUED", "Uploaded", "Queued"],
    ["PROCESSING", "RUNNING", "Processing", "Running"],
    ["REVIEW_REQUIRED", "WAITING_RETRY", "Review Required", "Waiting Retry"],
    ["APPROVED", "COMPLETED", "Approved", "Completed"],
    ["REJECTED", "FAILED", "Rejected", "Failed"],
    ["UNSUPPORTED", "COMPLETED", "Unsupported", "Completed"],
] as const)(
    "renders persisted %s and %s status",
    async (documentState, runState, documentLabel, runLabel) => {
        const getStatus = vi
            .fn<
                (
                    documentId: string,
                    signal?: AbortSignal,
                ) => Promise<DocumentStatus>
            >()
            .mockResolvedValue(status(documentState, runState));

        render(
            <DocumentStatusPanel
                api={{ getStatus }}
                documentId={DOCUMENT_ID}
            />,
            { wrapper: QueryWrapper },
        );

        expect(await screen.findByText(documentLabel)).toBeVisible();
        expect(screen.getByText(runLabel)).toBeVisible();
        expect(screen.getByText("invoice.pdf")).toBeVisible();
        expect(screen.getByText("2")).toBeVisible();
        expect(getStatus).toHaveBeenCalledWith(
            DOCUMENT_ID,
            expect.any(AbortSignal),
        );
    },
);

test("allows a failed status request to be retried", async () => {
    const getStatus = vi
        .fn<
            (
                documentId: string,
                signal?: AbortSignal,
            ) => Promise<DocumentStatus>
        >()
        .mockRejectedValueOnce(new Error("network unavailable"))
        .mockResolvedValueOnce(status("UPLOADED", "QUEUED"));

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
        "The persisted status could not be loaded.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry status" }));
    expect(await screen.findByText("invoice.pdf")).toBeVisible();
    expect(getStatus).toHaveBeenCalledTimes(2);
});

test("confirms when processing results are ready", async () => {
    const getStatus = vi
        .fn<
            (
                documentId: string,
                signal?: AbortSignal,
            ) => Promise<DocumentStatus>
        >()
        .mockResolvedValue(status("PROCESSING", "COMPLETED"));

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(
        await screen.findByText("Processing results are ready."),
    ).toBeVisible();
});

test("refreshes a completed run to reveal a later advisory proposal", async () => {
    const completed = status("APPROVED", "COMPLETED");
    const withProposal: DocumentStatus = {
        ...completed,
        current_run: {
            ...completed.current_run,
            ai_proposal: {
                schema_version: 1,
                provider: "OLLAMA",
                model_reference: "qwen3:8b",
                model_digest: null,
                prompt_version: "invoice-v1",
                selected_text_sha256: "a".repeat(64),
                status: "VALID",
                invoice_number: "INV-42",
                issue_date: "2026-09-16",
                supplier_name: "Acme Ltd",
                currency: "EUR",
                total_amount: "12.50",
                issues: [],
                proposed_at: "2026-09-16T12:00:06Z",
            },
        },
    };
    const getStatus = vi
        .fn<
            (
                documentId: string,
                signal?: AbortSignal,
            ) => Promise<DocumentStatus>
        >()
        .mockResolvedValueOnce(completed)
        .mockResolvedValueOnce(withProposal);

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(await screen.findByText("invoice.pdf")).toBeVisible();
    expect(
        screen.queryByText("AI proposal comparison"),
    ).not.toBeInTheDocument();
    fireEvent.click(
        screen.getByRole("button", { name: "Refresh document status" }),
    );
    expect(await screen.findByText("AI proposal comparison")).toBeVisible();
    expect(getStatus).toHaveBeenCalledTimes(2);
});

test("explains when processing requires an operator review", async () => {
    const getStatus = vi
        .fn<
            (
                documentId: string,
                signal?: AbortSignal,
            ) => Promise<DocumentStatus>
        >()
        .mockResolvedValue(status("REVIEW_REQUIRED", "REVIEW_REQUIRED"));

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(
        await screen.findByText("Processing requires an operator review."),
    ).toBeVisible();
});

test("explains why a completed unknown document is unsupported", async () => {
    const unsupported = status("UNSUPPORTED", "COMPLETED");
    unsupported.current_run.processing_output = {
        embedded_text: null,
        ocr_text: null,
        selected_text: null,
        classification: {
            document_type: "UNKNOWN",
            reason: "NO_MATCH",
            classified_at: "2026-09-15T08:00:02Z",
        },
        invoice_extraction: null,
        invoice_validation: null,
    };
    const getStatus = vi.fn().mockResolvedValue(unsupported);

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(
        await screen.findByText(
            "The document type could not be recognized. No structured extraction was performed.",
        ),
    ).toBeVisible();
    expect(
        screen.queryByText("Processing results are ready."),
    ).not.toBeInTheDocument();
});

test("shows the preceding run for a reprocessing lineage", async () => {
    const previousRunId = "33333333-3333-4333-8333-333333333333";
    const getStatus = vi
        .fn<
            (
                documentId: string,
                signal?: AbortSignal,
            ) => Promise<DocumentStatus>
        >()
        .mockResolvedValue({
            ...status("PROCESSING", "QUEUED"),
            current_run: {
                ...status("PROCESSING", "QUEUED").current_run,
                previous_run_id: previousRunId,
            },
        });

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(await screen.findByText("Previous processing run ID")).toBeVisible();
    expect(screen.getByText(previousRunId)).toBeVisible();
});

test("shows bounded failure evidence for a failed run", async () => {
    const failed = status("FAILED", "FAILED");
    const getStatus = vi.fn().mockResolvedValue({
        ...failed,
        current_run: {
            ...failed.current_run,
            failure: {
                stage: "EMBEDDED_TEXT_EXTRACTION",
                code: "ACTIVITY_RETRY_EXHAUSTED",
            },
        },
    });

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(
        await screen.findByText(
            "Processing stopped after a terminal technical failure.",
        ),
    ).toBeVisible();
    expect(screen.getByText("Embedded Text Extraction")).toBeVisible();
    expect(screen.getByText("ACTIVITY_RETRY_EXHAUSTED")).toBeVisible();
});

test("polls active states and stops for every terminal run state", () => {
    expect(statusPollInterval(undefined)).toBe(2_000);
    expect(statusPollInterval("QUEUED")).toBe(2_000);
    expect(statusPollInterval("RUNNING")).toBe(2_000);
    expect(statusPollInterval("COMPLETED")).toBe(false);
    expect(statusPollInterval("FAILED")).toBe(false);
    expect(statusPollInterval("CANCELLED")).toBe(false);
    expect(statusPollInterval("REVIEW_REQUIRED")).toBe(false);
});

function status(
    documentState: DocumentStatus["status"],
    runState: DocumentStatus["current_run"]["status"],
): DocumentStatus {
    return {
        id: DOCUMENT_ID,
        original_filename: "invoice.pdf",
        media_type: "application/pdf",
        size_bytes: 42_000,
        page_count: 1,
        content_sha256: "a".repeat(64),
        status: documentState,
        accepted_at: "2026-09-15T08:00:00Z",
        status_changed_at: "2026-09-15T08:00:00Z",
        current_run: {
            id: "22222222-2222-4222-8222-222222222222",
            previous_run_id: null,
            status: runState,
            queued_at: "2026-09-15T08:00:00Z",
            started_at: null,
            status_changed_at: "2026-09-15T08:00:00Z",
            finished_at: null,
            attempt_count: 2,
            failure: null,
            processing_output: null,
            review_resolution: null,
            ai_proposal: null,
            ai_proposal_failure: null,
        },
    };
}

function QueryWrapper({ children }: PropsWithChildren) {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
}
