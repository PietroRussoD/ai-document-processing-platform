import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { DocumentApi, DocumentStatus } from "../../api/documentApi";
import { ReviewDraftProvider } from "../document-review/ReviewDraftProvider";
import { ReviewResolutionPanel } from "../document-review/ReviewResolutionPanel";
import { DocumentReprocessingPanel } from "../document-reprocessing/DocumentReprocessingPanel";
import { OperatorAccessPanel } from "./OperatorAccessPanel";
import { OperatorTokenProvider } from "./OperatorTokenProvider";

const documentId = "11111111-1111-4111-8111-111111111111";
const run: DocumentStatus["current_run"] = {
    id: "22222222-2222-4222-8222-222222222222",
    previous_run_id: null,
    status: "REVIEW_REQUIRED",
    queued_at: "2026-10-15T08:00:00Z",
    started_at: null,
    status_changed_at: "2026-10-15T08:00:00Z",
    finished_at: null,
    attempt_count: 1,
    failure: null,
    processing_output: null,
    review_resolution: null,
    ai_proposal: null,
    ai_proposal_failure: null,
};

test("shares one in-memory token across review and reprocessing and clears PDF access without losing notes", async () => {
    const getSourceDocument = vi
        .fn<DocumentApi["getSourceDocument"]>()
        .mockResolvedValue(
            new Blob(["synthetic pdf"], { type: "application/pdf" }),
        );
    const resolveReview = vi
        .fn<DocumentApi["resolveReview"]>()
        .mockResolvedValue({
            processing_run_id: run.id,
            decision: "REJECT",
            reviewer_id: "operator-42",
            resolved_at: "2026-10-15T09:00:00Z",
            replayed: false,
        });
    const requestReprocessing = vi
        .fn<DocumentApi["requestReprocessing"]>()
        .mockResolvedValue({
            operation_id: "operation-42",
            document_id: documentId,
            source_run_id: run.id,
            replacement_run_id: "replacement-42",
            requested_at: "2026-10-15T10:00:00Z",
            replayed: false,
        });
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
        ...URL,
        createObjectURL: vi.fn(() => "blob:shared-source"),
        revokeObjectURL,
    });
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");
    const client = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    });
    function Workspace({ reprocess = false }: { reprocess?: boolean }) {
        return (
            <QueryClientProvider client={client}>
                <OperatorTokenProvider>
                    <ReviewDraftProvider>
                        <OperatorAccessPanel />
                        {reprocess ? (
                            <DocumentReprocessingPanel
                                api={{ requestReprocessing }}
                                documentId={documentId}
                                documentStatus="REJECTED"
                                run={{ ...run, status: "COMPLETED" }}
                                idempotencyKeyGenerator={() => "synthetic-key"}
                            />
                        ) : (
                            <ReviewResolutionPanel
                                api={{ getSourceDocument, resolveReview }}
                                documentId={documentId}
                                run={run}
                            />
                        )}
                    </ReviewDraftProvider>
                </OperatorTokenProvider>
            </QueryClientProvider>
        );
    }
    const view = render(<Workspace />);
    try {
        expect(screen.getAllByLabelText("Operator token")).toHaveLength(1);
        fireEvent.change(screen.getByLabelText("Operator token"), {
            target: { value: "synthetic-token" },
        });
        fireEvent.change(screen.getByLabelText(/Review note/), {
            target: { value: "Keep this draft." },
        });
        fireEvent.click(
            screen.getByRole("button", { name: "View source PDF" }),
        );
        await screen.findByTitle("Source PDF preview");
        fireEvent.click(screen.getByRole("button", { name: "Clear token" }));
        expect(screen.getByLabelText("Operator token")).toHaveValue("");
        expect(screen.getByLabelText("Operator token")).toHaveFocus();
        expect(
            screen.queryByTitle("Source PDF preview"),
        ).not.toBeInTheDocument();
        expect(revokeObjectURL).toHaveBeenCalledWith("blob:shared-source");
        expect(screen.getByLabelText(/Review note/)).toHaveValue(
            "Keep this draft.",
        );
        expect(
            screen.getByRole("button", { name: "View source PDF" }),
        ).toBeDisabled();
        fireEvent.change(screen.getByLabelText("Operator token"), {
            target: { value: "replacement-token" },
        });
        fireEvent.click(
            screen.getByRole("button", { name: "Reject document" }),
        );
        await waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Reject document" }),
            ).toBeEnabled(),
        );
        expect(resolveReview).toHaveBeenCalledWith(
            documentId,
            {
                decision: "REJECT",
                review_note: "Keep this draft.",
                corrections: [],
            },
            "replacement-token",
        );
        expect(screen.getByLabelText("Operator token")).toHaveValue(
            "replacement-token",
        );
        expect(screen.getByLabelText(/Review note/)).toHaveValue("");
        view.rerender(<Workspace reprocess />);
        expect(screen.getAllByLabelText("Operator token")).toHaveLength(1);
        expect(screen.getByLabelText("Operator token")).toHaveValue(
            "replacement-token",
        );
        fireEvent.change(screen.getByLabelText("Reprocessing reason"), {
            target: { value: "Retry synthetic invoice." },
        });
        fireEvent.click(
            screen.getByRole("button", { name: "Request reprocessing" }),
        );
        await screen.findByText("Reprocessing requested");
        expect(requestReprocessing).toHaveBeenCalledWith(
            documentId,
            { reason: "Retry synthetic invoice." },
            "replacement-token",
            "synthetic-key",
        );
        expect(screen.getByLabelText("Operator token")).toHaveValue(
            "replacement-token",
        );
        expect(storageWrite).not.toHaveBeenCalled();
        view.rerender(<div />);
        view.rerender(<Workspace />);
        expect(screen.getByLabelText("Operator token")).toHaveValue("");
    } finally {
        view.unmount();
        storageWrite.mockRestore();
        vi.unstubAllGlobals();
        client.clear();
    }
});
