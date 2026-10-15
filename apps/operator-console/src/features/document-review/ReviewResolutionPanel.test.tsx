import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type PropsWithChildren } from "react";
import { expect, test, vi } from "vitest";

import {
    type DocumentApi,
    DocumentApiProblem,
    type DocumentStatus,
    type ReviewResolution,
} from "../../api/documentApi";
import { axe } from "../../test/accessibility";
import { ReviewResolutionPanel } from "./ReviewResolutionPanel";
import { ReviewDraftProvider } from "./ReviewDraftProvider";
import { DocumentWorkQueuesPanel } from "../document-work-queues/DocumentWorkQueuesPanel";

const DOCUMENT_ID = "11111111-1111-4111-8111-111111111111";

test("refreshes cached work queues after a successful review", async () => {
    const client = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    });
    const listWorkQueue = vi
        .fn<DocumentApi["listWorkQueue"]>()
        .mockResolvedValue({ items: [], total: 0, offset: 0, limit: 25 });
    const resolveReview = vi
        .fn<DocumentApi["resolveReview"]>()
        .mockResolvedValue({
            processing_run_id: "22222222-2222-4222-8222-222222222222",
            decision: "REJECT",
            reviewer_id: "operator-42",
            resolved_at: "2026-09-17T18:00:00Z",
            replayed: false,
        });
    render(
        <QueryClientProvider client={client}>
            <DocumentWorkQueuesPanel
                api={{ listWorkQueue }}
                selectedDocumentId={DOCUMENT_ID}
                onSelectDocument={() => undefined}
            />
            <ReviewResolutionPanel
                api={{ resolveReview }}
                documentId={DOCUMENT_ID}
                run={reviewRequiredRun()}
            />
        </QueryClientProvider>,
    );
    await waitFor(() => expect(listWorkQueue).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "operator-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject document" }));
    await waitFor(() => expect(listWorkQueue).toHaveBeenCalledTimes(2));
});

test("submits an approval with the token and optional note", async () => {
    let completeReview!: (resolution: ReviewResolution) => void;
    const reviewCompletion = new Promise<ReviewResolution>((resolve) => {
        completeReview = resolve;
    });
    const resolveReview = vi
        .fn<DocumentApi["resolveReview"]>()
        .mockReturnValue(reviewCompletion);

    render(
        <ReviewResolutionPanel
            api={{ resolveReview }}
            documentId={DOCUMENT_ID}
            run={reviewRequiredRunWithInvoice()}
        />,
        { wrapper: QueryWrapper },
    );

    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "operator-token" },
    });
    fireEvent.change(screen.getByLabelText(/Review note/), {
        target: { value: "Checked the supplier statement." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve document" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
        "Saving review decision",
    );
    expect(resolveReview).toHaveBeenCalledWith(
        DOCUMENT_ID,
        {
            decision: "APPROVE",
            review_note: "Checked the supplier statement.",
            corrections: [],
        },
        "operator-token",
    );
    completeReview({
        processing_run_id: "22222222-2222-4222-8222-222222222222",
        decision: "APPROVE",
        reviewer_id: "operator-42",
        resolved_at: "2026-09-17T18:00:00Z",
        replayed: false,
    });
    await waitFor(() => {
        expect(screen.getByLabelText("Operator token")).toHaveValue("");
    });
});

test("shows a safe review failure message", async () => {
    const problem = {
        type: "urn:problem:review-authentication-rejected",
        title: "Review authentication rejected",
        status: 401,
        detail: "review authentication was rejected",
    };
    const resolveReview = vi
        .fn<DocumentApi["resolveReview"]>()
        .mockRejectedValue(new DocumentApiProblem(problem));

    render(
        <ReviewResolutionPanel
            api={{ resolveReview }}
            documentId={DOCUMENT_ID}
            run={reviewRequiredRun()}
        />,
        { wrapper: QueryWrapper },
    );

    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "incorrect-token" },
    });
    fireEvent.change(screen.getByLabelText(/Review note/), {
        target: { value: "Unfinished review." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject document" }));

    const errorMessage = await screen.findByRole("alert");
    expect(errorMessage).toHaveTextContent(problem.detail);
    expect(errorMessage).toHaveFocus();
    expect(screen.getByLabelText("Operator token")).toHaveAttribute(
        "aria-describedby",
        "review-token-help review-resolution-error",
    );
    expect(screen.getByLabelText(/Review note/)).toHaveValue(
        "Unfinished review.",
    );
    const leaving = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(leaving);
    expect(leaving.defaultPrevented).toBe(true);
});

test("restores AI and manual correction sources without restoring credentials and clears a saved draft", async () => {
    let completeReview!: (resolution: ReviewResolution) => void;
    const reviewCompletion = new Promise<ReviewResolution>((resolve) => {
        completeReview = resolve;
    });
    const resolveReview = vi
        .fn<DocumentApi["resolveReview"]>()
        .mockReturnValue(reviewCompletion);
    const run = reviewRequiredRunWithInvoice();
    run.ai_proposal = {
        schema_version: 1,
        provider: "OLLAMA",
        model_reference: "synthetic-model",
        model_digest: null,
        prompt_version: "invoice-v1",
        selected_text_sha256: "a".repeat(64),
        status: "VALID",
        invoice_number: "INV-2026-001",
        issue_date: "2026-09-17",
        supplier_name: "Suggested Synthetic Supplier",
        currency: "EUR",
        total_amount: "149.9900",
        issues: [],
        proposed_at: "2026-09-17T18:00:00Z",
    };
    const { rerender } = render(
        <ReviewResolutionPanel
            key="first"
            api={{ resolveReview }}
            documentId={DOCUMENT_ID}
            run={run}
        />,
        { wrapper: QueryWrapper },
    );
    fireEvent.click(
        screen.getByRole("button", { name: "Use suggestion for Supplier" }),
    );
    fireEvent.change(screen.getByLabelText("Total amount"), {
        target: { value: "159.99" },
    });
    fireEvent.change(screen.getByLabelText(/Review note/), {
        target: { value: "Verified against the source." },
    });
    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "synthetic-token" },
    });

    rerender(
        <ReviewResolutionPanel
            key="second"
            api={{ resolveReview }}
            documentId="33333333-3333-4333-8333-333333333333"
            run={run}
        />,
    );
    expect(screen.getByLabelText("Supplier")).toHaveValue("Acme Supplies Ltd");
    const leavingAnotherDocument = new Event("beforeunload", {
        cancelable: true,
    });
    window.dispatchEvent(leavingAnotherDocument);
    expect(leavingAnotherDocument.defaultPrevented).toBe(true);

    rerender(
        <ReviewResolutionPanel
            key="first"
            api={{ resolveReview }}
            documentId={DOCUMENT_ID}
            run={run}
        />,
    );
    expect(screen.getByLabelText("Supplier")).toHaveValue(
        "Suggested Synthetic Supplier",
    );
    expect(screen.getByLabelText("Total amount")).toHaveValue(159.99);
    expect(screen.getByLabelText(/Review note/)).toHaveValue(
        "Verified against the source.",
    );
    expect(screen.getByLabelText("Operator token")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "new-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve document" }));
    expect(await screen.findByText("Saving review decision")).toBeVisible();
    expect(screen.getByLabelText("Supplier")).toBeDisabled();
    expect(screen.getByLabelText("Total amount")).toBeDisabled();
    expect(
        screen.getByRole("button", {
            name: "Suggestion selected for Supplier",
        }),
    ).toBeDisabled();
    completeReview({
        processing_run_id: "22222222-2222-4222-8222-222222222222",
        decision: "APPROVE",
        reviewer_id: "operator-42",
        resolved_at: "2026-09-17T18:00:00Z",
        replayed: false,
    });
    await waitFor(() =>
        expect(screen.getByLabelText("Operator token")).toHaveValue(""),
    );
    expect(resolveReview).toHaveBeenCalledWith(
        DOCUMENT_ID,
        {
            decision: "APPROVE",
            review_note: "Verified against the source.",
            corrections: [
                {
                    field: "SUPPLIER_NAME",
                    corrected_value: "Suggested Synthetic Supplier",
                    source: "AI_PROPOSAL",
                },
                {
                    field: "TOTAL_AMOUNT",
                    corrected_value: "159.99",
                    source: "MANUAL",
                },
            ],
        },
        "new-token",
    );
    const leavingAfterSave = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(leavingAfterSave);
    expect(leavingAfterSave.defaultPrevented).toBe(false);
});

test("loads the source PDF only on request and revokes its object URL on close", async () => {
    const pdf = new Blob(["synthetic pdf"], { type: "application/pdf" });
    const getSourceDocument = vi
        .fn<DocumentApi["getSourceDocument"]>()
        .mockResolvedValue(pdf);
    const createObjectURL = vi.fn(() => "blob:source-document");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
        ...URL,
        createObjectURL,
        revokeObjectURL,
    });
    const user = userEvent.setup();

    const { container } = render(
        <ReviewResolutionPanel
            api={{
                resolveReview: vi.fn(),
                getSourceDocument,
            }}
            documentId={DOCUMENT_ID}
            run={reviewRequiredRun()}
        />,
        { wrapper: QueryWrapper },
    );

    expect(getSourceDocument).not.toHaveBeenCalled();
    expect(
        screen.getByRole("button", { name: "View source PDF" }),
    ).toBeDisabled();
    expect((await axe(container)).violations).toEqual([]);

    await user.type(screen.getByLabelText("Operator token"), "operator-token");
    await user.click(screen.getByRole("button", { name: "View source PDF" }));

    expect(getSourceDocument).toHaveBeenCalledWith(
        DOCUMENT_ID,
        "operator-token",
        expect.any(AbortSignal),
    );
    expect(await screen.findByTitle("Source PDF preview")).toHaveAttribute(
        "src",
        "blob:source-document",
    );
    expect(
        screen.getByRole("link", { name: "Open PDF in new tab" }),
    ).toHaveAttribute("href", "blob:source-document");
    expect(
        screen.getByRole("link", { name: "Open PDF in new tab" }),
    ).toHaveAttribute("rel", "noopener noreferrer");
    const preview = screen.getByTitle("Source PDF preview");
    await user.click(screen.getByRole("button", { name: "Invoice fields" }));
    await user.type(
        screen.getByLabelText(/Review note/),
        "Check the source amount.",
    );
    await user.click(screen.getByRole("button", { name: "Source PDF" }));
    expect(screen.getByRole("button", { name: "Source PDF" })).toHaveAttribute(
        "aria-pressed",
        "true",
    );
    expect(screen.getByTitle("Source PDF preview")).toBe(preview);
    expect(getSourceDocument).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Invoice fields" }));
    expect(screen.getByLabelText(/Review note/)).toHaveValue(
        "Check the source amount.",
    );
    expect(screen.getByLabelText("Operator token")).toHaveValue(
        "operator-token",
    );
    await user.click(screen.getByRole("button", { name: "Source PDF" }));
    await user.click(screen.getByRole("button", { name: "Close source PDF" }));
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:source-document");
    expect(screen.queryByTitle("Source PDF preview")).not.toBeInTheDocument();
    expect(
        screen.queryByRole("link", { name: "Open PDF in new tab" }),
    ).not.toBeInTheDocument();
    vi.unstubAllGlobals();
});

test("shows a safe message when loading the source PDF fails", async () => {
    const getSourceDocument = vi
        .fn<DocumentApi["getSourceDocument"]>()
        .mockRejectedValue(new Error("private storage path"));
    const user = userEvent.setup();

    render(
        <ReviewResolutionPanel
            api={{ resolveReview: vi.fn(), getSourceDocument }}
            documentId={DOCUMENT_ID}
            run={reviewRequiredRun()}
        />,
        { wrapper: QueryWrapper },
    );
    await user.type(screen.getByLabelText("Operator token"), "operator-token");
    await user.click(screen.getByRole("button", { name: "View source PDF" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
        "The source PDF could not be loaded.",
    );
    expect(screen.queryByText("private storage path")).not.toBeInTheDocument();
});

test("aborts a source-PDF request when the review panel unmounts", async () => {
    let requestSignal: AbortSignal | undefined;
    const getSourceDocument = vi
        .fn<DocumentApi["getSourceDocument"]>()
        .mockImplementation((_documentId, _operatorToken, signal) => {
            requestSignal = signal;
            return new Promise(() => undefined);
        });
    const user = userEvent.setup();
    const { unmount } = render(
        <ReviewResolutionPanel
            api={{ resolveReview: vi.fn(), getSourceDocument }}
            documentId={DOCUMENT_ID}
            run={reviewRequiredRun()}
        />,
        { wrapper: QueryWrapper },
    );
    await user.type(screen.getByLabelText("Operator token"), "operator-token");
    await user.click(screen.getByRole("button", { name: "View source PDF" }));

    expect(requestSignal?.aborted).toBe(false);
    unmount();
    expect(requestSignal?.aborted).toBe(true);
});

test("shows the immutable outcome after a refresh", () => {
    render(
        <ReviewResolutionPanel
            documentId={DOCUMENT_ID}
            run={{
                ...reviewRequiredRun(),
                status: "COMPLETED",
                review_resolution: {
                    decision: "REJECT",
                    reviewer_id: "operator-42",
                    review_note: "Missing supplier evidence.",
                    resolved_at: "2026-09-17T18:00:00Z",
                    corrections: [],
                },
            }}
        />,
        { wrapper: QueryWrapper },
    );

    expect(screen.getByText("Review resolved")).toBeVisible();
    expect(screen.getByText("Rejected")).toBeVisible();
    expect(screen.getByText("operator-42")).toBeVisible();
    expect(screen.getByText("Missing supplier evidence.")).toBeVisible();
    expect(screen.queryByLabelText("Operator token")).not.toBeInTheDocument();
});

test("has no detectable accessibility violations while a review is required", async () => {
    const { container } = render(
        <ReviewResolutionPanel
            documentId={DOCUMENT_ID}
            run={reviewRequiredRun()}
        />,
        { wrapper: QueryWrapper },
    );

    expect((await axe(container)).violations).toEqual([]);
});

function reviewRequiredRun(): DocumentStatus["current_run"] {
    return {
        id: "22222222-2222-4222-8222-222222222222",
        previous_run_id: null,
        status: "REVIEW_REQUIRED",
        queued_at: "2026-09-17T17:00:00Z",
        started_at: "2026-09-17T17:00:01Z",
        status_changed_at: "2026-09-17T17:00:02Z",
        finished_at: null,
        attempt_count: 1,
        failure: null,
        processing_output: null,
        review_resolution: null,
        ai_proposal: null,
        ai_proposal_failure: null,
    };
}

function reviewRequiredRunWithInvoice(): DocumentStatus["current_run"] {
    return {
        ...reviewRequiredRun(),
        processing_output: {
            embedded_text: null,
            ocr_text: null,
            selected_text: null,
            classification: null,
            invoice_extraction: {
                method: "DETERMINISTIC_RULES",
                invoice_number: "INV-2026-001",
                issue_date: "2026-09-17",
                supplier_name: "Acme Supplies Ltd",
                currency: "EUR",
                total_amount: "149.9900",
                extracted_at: "2026-09-17T18:00:00Z",
            },
            invoice_validation: null,
        },
    };
}

function QueryWrapper({ children }: PropsWithChildren) {
    const client = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    });
    return (
        <QueryClientProvider client={client}>
            <ReviewDraftProvider>{children}</ReviewDraftProvider>
        </QueryClientProvider>
    );
}
