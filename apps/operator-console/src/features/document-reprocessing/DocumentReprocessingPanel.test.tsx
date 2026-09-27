import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type PropsWithChildren } from "react";
import { expect, test, vi } from "vitest";

import {
    type DocumentApi,
    DocumentApiProblem,
    type DocumentStatus,
} from "../../api/documentApi";
import { axe } from "../../test/accessibility";
import { DocumentReprocessingPanel } from "./DocumentReprocessingPanel";

const DOCUMENT_ID = "11111111-1111-4111-8111-111111111111";

test("submits a terminal run for controlled reprocessing", async () => {
    const requestReprocessing = vi
        .fn<DocumentApi["requestReprocessing"]>()
        .mockResolvedValue({
            operation_id: "33333333-3333-4333-8333-333333333333",
            document_id: DOCUMENT_ID,
            source_run_id: "22222222-2222-4222-8222-222222222222",
            replacement_run_id: "44444444-4444-4444-8444-444444444444",
            requested_at: "2026-09-20T12:00:00Z",
            replayed: false,
        });

    render(
        <DocumentReprocessingPanel
            api={{ requestReprocessing }}
            documentId={DOCUMENT_ID}
            idempotencyKeyGenerator={() => "reprocess-42"}
            run={terminalRun()}
        />,
        { wrapper: QueryWrapper },
    );

    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "operator-token" },
    });
    fireEvent.change(screen.getByLabelText("Reprocessing reason"), {
        target: { value: "Retry after the upstream OCR outage was resolved." },
    });
    fireEvent.click(
        screen.getByRole("button", { name: "Request reprocessing" }),
    );

    await waitFor(() => {
        expect(requestReprocessing).toHaveBeenCalledWith(
            DOCUMENT_ID,
            { reason: "Retry after the upstream OCR outage was resolved." },
            "operator-token",
            "reprocess-42",
        );
    });
    await waitFor(() => {
        expect(screen.getByText("Reprocessing requested")).toBeVisible();
    });
    expect(screen.queryByLabelText("Operator token")).not.toBeInTheDocument();
    expect(
        screen.queryByLabelText("Reprocessing reason"),
    ).not.toBeInTheDocument();
    expect(
        screen.getByText("33333333-3333-4333-8333-333333333333"),
    ).toBeVisible();
    expect(
        screen.getByText("44444444-4444-4444-8444-444444444444"),
    ).toBeVisible();
});

test("keeps the idempotency key when a request can be retried", async () => {
    const problem = {
        type: "urn:problem:reprocessing-conflict",
        title: "Reprocessing unavailable",
        status: 409,
        detail: "processing run is not terminal",
    };
    const requestReprocessing = vi
        .fn<DocumentApi["requestReprocessing"]>()
        .mockRejectedValue(new DocumentApiProblem(problem));
    const idempotencyKeyGenerator = vi.fn(() => "reprocess-42");

    render(
        <DocumentReprocessingPanel
            api={{ requestReprocessing }}
            documentId={DOCUMENT_ID}
            idempotencyKeyGenerator={idempotencyKeyGenerator}
            run={terminalRun()}
        />,
        { wrapper: QueryWrapper },
    );

    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "operator-token" },
    });
    fireEvent.change(screen.getByLabelText("Reprocessing reason"), {
        target: { value: "Retry after the upstream OCR outage was resolved." },
    });
    fireEvent.click(
        screen.getByRole("button", { name: "Request reprocessing" }),
    );
    await screen.findByRole("alert");
    fireEvent.click(
        screen.getByRole("button", { name: "Request reprocessing" }),
    );

    expect(idempotencyKeyGenerator).toHaveBeenCalledOnce();
    expect(requestReprocessing).toHaveBeenLastCalledWith(
        DOCUMENT_ID,
        { reason: "Retry after the upstream OCR outage was resolved." },
        "operator-token",
        "reprocess-42",
    );
});

test("does not show reprocessing controls for an active run", () => {
    render(
        <DocumentReprocessingPanel
            documentId={DOCUMENT_ID}
            run={activeRun()}
        />,
        { wrapper: QueryWrapper },
    );

    expect(
        screen.queryByRole("heading", {
            name: "Request controlled reprocessing",
        }),
    ).not.toBeInTheDocument();
});

test("has no detectable accessibility violations for a terminal run", async () => {
    const { container } = render(
        <DocumentReprocessingPanel
            documentId={DOCUMENT_ID}
            run={terminalRun()}
        />,
        { wrapper: QueryWrapper },
    );

    expect((await axe(container)).violations).toEqual([]);
});

function terminalRun(): DocumentStatus["current_run"] {
    return {
        ...activeRun(),
        status: "COMPLETED",
        started_at: "2026-09-20T11:00:01Z",
        finished_at: "2026-09-20T11:00:02Z",
    };
}

function activeRun(): DocumentStatus["current_run"] {
    return {
        id: "22222222-2222-4222-8222-222222222222",
        previous_run_id: null,
        status: "RUNNING",
        queued_at: "2026-09-20T11:00:00Z",
        started_at: "2026-09-20T11:00:01Z",
        status_changed_at: "2026-09-20T11:00:01Z",
        finished_at: null,
        attempt_count: 1,
        failure: null,
        processing_output: null,
        review_resolution: null,
        ai_proposal: null,
        ai_proposal_failure: null,
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
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
}
