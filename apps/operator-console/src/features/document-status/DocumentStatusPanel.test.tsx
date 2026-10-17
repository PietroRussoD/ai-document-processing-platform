import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
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
                    _operatorToken: string,
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
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByText("2")).toBeVisible();
        expect(getStatus).toHaveBeenCalledWith(
            DOCUMENT_ID,
            "",
            expect.any(AbortSignal),
        );
    },
);

test.each([
    ["automatic", "Approved automatically"],
    ["operator", "Approved by an operator"],
    ["unknown", "Document approved"],
    ["review-required-only", "Document approved"],
] as const)(
    "identifies approval from persisted %s evidence",
    async (origin, title) => {
        const document = status("APPROVED", "COMPLETED");
        if (
            origin === "automatic" ||
            origin === "operator" ||
            origin === "review-required-only"
        ) {
            document.current_run.processing_output = {
                embedded_text: null,
                ocr_text: null,
                selected_text: null,
                classification: null,
                invoice_extraction: null,
                invoice_validation: {
                    decision:
                        origin === "automatic"
                            ? "AUTO_APPROVE"
                            : "REVIEW_REQUIRED",
                    issues: origin === "automatic" ? [] : ["MISSING_CURRENCY"],
                    validated_at: "2026-09-15T08:00:00Z",
                },
            };
        }
        if (origin === "operator") {
            document.current_run.review_resolution = {
                decision: "APPROVE",
                reviewer_id: "operator-42",
                review_note: null,
                resolved_at: "2026-09-15T09:00:00Z",
                corrections: [],
            };
        }
        render(
            <DocumentStatusPanel
                api={{ getStatus: vi.fn().mockResolvedValue(document) }}
                documentId={DOCUMENT_ID}
            />,
            { wrapper: QueryWrapper },
        );
        expect(await screen.findByText(title)).toBeVisible();
        if (origin === "automatic") {
            expect(
                screen.getByText(/No operator review was needed/),
            ).toBeVisible();
            expect(
                screen.queryByText("Review resolved"),
            ).not.toBeInTheDocument();
        } else if (origin === "operator") {
            expect(screen.getByText("operator-42")).toBeVisible();
            expect(
                screen.queryByText("Approved automatically"),
            ).not.toBeInTheDocument();
        } else {
            expect(
                screen.getByText(/available records do not identify how/),
            ).toBeVisible();
            expect(
                screen.queryByText("Approved by an operator"),
            ).not.toBeInTheDocument();
        }
    },
);

test("allows a failed status request to be retried", async () => {
    const getStatus = vi
        .fn<
            (
                documentId: string,
                _operatorToken: string,
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
        "The document details could not be loaded.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry loading" }));
    expect(await screen.findByText("invoice.pdf")).toBeVisible();
    expect(getStatus).toHaveBeenCalledTimes(2);
});

test("explains that an active document is still being processed", async () => {
    const getStatus = vi
        .fn<
            (
                documentId: string,
                _operatorToken: string,
                signal?: AbortSignal,
            ) => Promise<DocumentStatus>
        >()
        .mockResolvedValue(status("PROCESSING", "RUNNING"));

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(await screen.findByText("Processing in progress")).toBeVisible();
    expect(
        screen.getByRole("region", { name: "Processing progress" }),
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
                _operatorToken: string,
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
    fireEvent.click(screen.getByText("Processing results and AI details"));
    fireEvent.click(
        screen.getByRole("button", { name: "Refresh document status" }),
    );
    expect(await screen.findByText("AI proposal comparison")).toBeVisible();
    expect(getStatus).toHaveBeenCalledTimes(2);
});

test("explains when processing requires an operator review", async () => {
    const reviewing = status("REVIEW_REQUIRED", "REVIEW_REQUIRED");
    reviewing.current_run.processing_output = {
        embedded_text: null,
        ocr_text: null,
        selected_text: null,
        classification: null,
        invoice_extraction: {
            method: "DETERMINISTIC_RULES",
            invoice_number: "INV-SYNTHETIC",
            issue_date: "2026-09-15",
            supplier_name: "Synthetic Supplier",
            currency: null,
            total_amount: null,
            extracted_at: "2026-09-15T08:00:00Z",
        },
        invoice_validation: {
            decision: "REVIEW_REQUIRED",
            issues: ["MISSING_CURRENCY", "MISSING_TOTAL_AMOUNT"],
            validated_at: "2026-09-15T08:00:00Z",
        },
    };
    const getStatus = vi
        .fn<
            (
                documentId: string,
                _operatorToken: string,
                signal?: AbortSignal,
            ) => Promise<DocumentStatus>
        >()
        .mockResolvedValue(reviewing);

    render(
        <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />,
        { wrapper: QueryWrapper },
    );

    expect(
        await screen.findByText("Action required: review this document"),
    ).toBeVisible();
    expect(
        screen.getByRole("link", { name: "Go to review form" }),
    ).toHaveAttribute("href", "#review-resolution-heading");
    expect(
        within(
            screen.getByRole("list", { name: "Reasons for review" }),
        ).getByText("Missing Currency"),
    ).toBeVisible();
    const review = screen.getByRole("region", {
        name: "Resolve operator review",
    });
    const results = screen.getByRole("region", {
        name: "Processing results",
        hidden: true,
    });
    expect(review).toBeVisible();
    expect(
        screen.getByRole("region", {
            name: "Processing progress",
            hidden: true,
        }),
    ).not.toBeVisible();
    expect(results).not.toBeVisible();
    expect(
        review.compareDocumentPosition(results) &
            Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Supplier"), {
        target: { value: "Corrected Supplier" },
    });
    fireEvent.click(screen.getByText("Processing results and AI details"));
    expect(results).toBeVisible();
    fireEvent.click(screen.getByText("Processing results and AI details"));
    expect(screen.getByLabelText("Supplier")).toHaveValue("Corrected Supplier");
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
    expect(
        screen.getByText(
            /Reprocessing is unavailable for unsupported documents/,
        ),
    ).toBeVisible();
    expect(
        screen.queryByRole("button", { name: "Request reprocessing" }),
    ).not.toBeInTheDocument();
});

test("shows the preceding run for a reprocessing lineage", async () => {
    const previousRunId = "33333333-3333-4333-8333-333333333333";
    const getStatus = vi
        .fn<
            (
                documentId: string,
                _operatorToken: string,
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

    fireEvent.click(await screen.findByText("Technical details"));
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
        await screen.findByText("Processing stopped after a technical failure"),
    ).toBeVisible();
    fireEvent.click(screen.getByText("Technical details"));
    expect(screen.getByText("Embedded Text Extraction")).toBeVisible();
    expect(screen.getByText("ACTIVITY_RETRY_EXHAUSTED")).toBeVisible();
});

test("polls active states and stops for every terminal run state", () => {
    expect(statusPollInterval(undefined)).toBe(2_000);
    expect(statusPollInterval(status("UPLOADED", "QUEUED").current_run)).toBe(
        2_000,
    );
    expect(
        statusPollInterval(status("PROCESSING", "RUNNING").current_run),
    ).toBe(2_000);
    expect(
        statusPollInterval(status("APPROVED", "COMPLETED").current_run),
    ).toBe(false);
    expect(statusPollInterval(status("FAILED", "FAILED").current_run)).toBe(
        false,
    );
    expect(
        statusPollInterval(status("PROCESSING", "CANCELLED").current_run),
    ).toBe(false);
    expect(
        statusPollInterval(
            status("REVIEW_REQUIRED", "REVIEW_REQUIRED").current_run,
        ),
    ).toBe(false);
});

test("polls across deterministic completion and AI start, then stops at AI completion", async () => {
    vi.useFakeTimers();
    const at = "2026-09-29T10:00:00Z";
    vi.setSystemTime(new Date(at));
    const initial = status("APPROVED", "COMPLETED");
    initial.current_run.status_changed_at = at;
    initial.current_run.processing_output = {
        embedded_text: null,
        ocr_text: null,
        selected_text: null,
        classification: {
            document_type: "INVOICE",
            reason: "KEYWORD_MATCHED",
            classified_at: at,
        },
        invoice_extraction: null,
        invoice_validation: null,
    };
    const running: DocumentStatus = {
        ...initial,
        current_run: {
            ...initial.current_run,
            ai_execution: {
                status: "RUNNING",
                started_at: at,
                finished_at: null,
                status_changed_at: at,
            },
        },
    };
    const completed: DocumentStatus = {
        ...initial,
        current_run: {
            ...initial.current_run,
            ai_execution: {
                status: "COMPLETED",
                started_at: at,
                finished_at: at,
                status_changed_at: at,
            },
        },
    };
    const getStatus = vi
        .fn()
        .mockResolvedValueOnce(running)
        .mockResolvedValue(completed);
    const client = new QueryClient({
        defaultOptions: {
            queries: { retry: false, refetchOnMount: false, gcTime: Infinity },
        },
    });
    client.setQueryData(["document-status", DOCUMENT_ID], initial);
    const view = render(
        <QueryClientProvider client={client}>
            <DocumentStatusPanel api={{ getStatus }} documentId={DOCUMENT_ID} />
        </QueryClientProvider>,
    );
    try {
        fireEvent.click(screen.getByText("Processing results and AI details"));
        fireEvent.click(screen.getByText("Processing history"));
        const unrecordedMessages = screen.getAllByText(
            "AI execution state is not recorded.",
        );
        expect(unrecordedMessages).toHaveLength(2);
        for (const message of unrecordedMessages) expect(message).toBeVisible();
        await act(async () => {
            await vi.advanceTimersByTimeAsync(2_001);
        });
        expect(screen.getByText("AI proposal pending.")).toBeVisible();
        await act(async () => {
            await vi.advanceTimersByTimeAsync(2_001);
        });
        expect(screen.getByText("Execution completed")).toBeVisible();
        expect(getStatus).toHaveBeenCalledTimes(2);
        await act(async () => {
            await vi.advanceTimersByTimeAsync(10_000);
        });
        expect(getStatus).toHaveBeenCalledTimes(2);
    } finally {
        view.unmount();
        client.clear();
        vi.useRealTimers();
    }
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
