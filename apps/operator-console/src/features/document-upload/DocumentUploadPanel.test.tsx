import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { type PropsWithChildren } from "react";
import { expect, type Mock, test, vi } from "vitest";

import {
    type AcceptedDocument,
    type DocumentStatus,
    DocumentApiProblem,
} from "../../api/documentApi";
import { DocumentUploadPanel } from "./DocumentUploadPanel";

const acceptedDocument: AcceptedDocument = {
    document_id: "11111111-1111-4111-8111-111111111111",
    processing_run_id: "22222222-2222-4222-8222-222222222222",
    accepted_at: "2026-09-14T19:00:00Z",
    replayed: false,
};

const persistedStatus: DocumentStatus = {
    id: acceptedDocument.document_id,
    original_filename: "invoice.pdf",
    media_type: "application/pdf",
    size_bytes: 3,
    page_count: 1,
    content_sha256: "a".repeat(64),
    status: "UPLOADED",
    accepted_at: acceptedDocument.accepted_at,
    status_changed_at: acceptedDocument.accepted_at,
    current_run: {
        id: acceptedDocument.processing_run_id,
        status: "QUEUED",
        queued_at: acceptedDocument.accepted_at,
        started_at: null,
        status_changed_at: acceptedDocument.accepted_at,
        finished_at: null,
        attempt_count: 0,
    },
};

type UploadFunction = (
    document: File,
    idempotencyKey: string,
) => Promise<AcceptedDocument>;

test("uploads the selected PDF and renders its durable identifiers", async () => {
    const upload = vi.fn<UploadFunction>().mockResolvedValue(acceptedDocument);
    renderPanel(upload);
    const document = selectPdf();

    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));

    expect(await screen.findByText("Document accepted")).toBeVisible();
    expect(upload).toHaveBeenCalledWith(document, "stable-upload-key");
    expect(screen.getByText(acceptedDocument.document_id)).toBeVisible();
    expect(screen.getByText(acceptedDocument.processing_run_id)).toBeVisible();
    expect(
        screen.getByRole("button", { name: "Upload document" }),
    ).toBeDisabled();
});

test("keeps the idempotency key stable when retrying a rejected request", async () => {
    const problem = {
        type: "urn:problem:invalid-pdf",
        title: "Invalid PDF",
        status: 422,
        detail: "The PDF structure is invalid.",
    };
    const upload = vi
        .fn<UploadFunction>()
        .mockRejectedValueOnce(new DocumentApiProblem(problem))
        .mockResolvedValueOnce({ ...acceptedDocument, replayed: true });
    renderPanel(upload);
    const document = selectPdf();

    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(problem.detail);

    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByText("Previously accepted")).toBeVisible();
    expect(upload).toHaveBeenNthCalledWith(1, document, "stable-upload-key");
    expect(upload).toHaveBeenNthCalledWith(2, document, "stable-upload-key");
});

test("shows a safe message for unexpected failures", async () => {
    const upload = vi
        .fn<UploadFunction>()
        .mockRejectedValue(new Error("internal network detail"));
    renderPanel(upload);
    selectPdf();

    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
        "The document could not be uploaded. Try again.",
    );
    expect(
        screen.queryByText("internal network detail"),
    ).not.toBeInTheDocument();
});

function renderPanel(
    upload: Mock<UploadFunction>,
    getStatus = vi
        .fn<
            (
                documentId: string,
                signal?: AbortSignal,
            ) => Promise<DocumentStatus>
        >()
        .mockResolvedValue(persistedStatus),
) {
    return render(
        <DocumentUploadPanel
            api={{ getStatus, upload }}
            idGenerator={() => "stable-upload-key"}
        />,
        { wrapper: QueryWrapper },
    );
}

function selectPdf(): File {
    const document = new File(["pdf"], "invoice.pdf", {
        type: "application/pdf",
    });
    fireEvent.change(screen.getByLabelText("Choose a PDF"), {
        target: { files: [document] },
    });
    return document;
}

function QueryWrapper({ children }: PropsWithChildren) {
    const client = new QueryClient({
        defaultOptions: { mutations: { retry: false } },
    });
    return (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
}
