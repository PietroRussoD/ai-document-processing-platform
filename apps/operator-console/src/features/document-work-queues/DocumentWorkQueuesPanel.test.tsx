import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/react";
import { type PropsWithChildren } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import {
    type DocumentApi,
    type DocumentStatus,
    type DocumentWorkQueuePage,
} from "../../api/documentApi";
import { DocumentWorkQueuesPanel } from "./DocumentWorkQueuesPanel";

const documentId = "11111111-1111-4111-8111-111111111111";
const runId = "22222222-2222-4222-8222-222222222222";
const acceptedAt = "2026-09-22T12:00:00Z";

beforeEach(() => {
    window.history.replaceState({}, "", "/");
});

test("shows an active document and opens its persisted detail", async () => {
    const item = queueItem({
        status: "PROCESSING",
        processing_run_status: "RUNNING",
    });
    const api = createApi({
        listWorkQueue: vi.fn().mockResolvedValue(queuePage([item])),
        getStatus: vi.fn().mockResolvedValue(documentStatus()),
    });

    renderPanel(api);

    const row = (await screen.findByText("invoice-42.pdf")).closest("li");
    expect(row).not.toBeNull();
    expect(screen.getByText("PROCESSING")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "View details" }));

    expect(new URL(window.location.href).searchParams.get("documentId")).toBe(
        documentId,
    );
    expect(row).toContainElement(
        await screen.findByRole("region", { name: "invoice-42.pdf" }),
    );
    expect(api.getStatus).toHaveBeenCalledWith(
        documentId,
        expect.any(AbortSignal),
    );

    fireEvent.click(screen.getByRole("button", { name: "Hide details" }));
    expect(new URL(window.location.href).searchParams.has("documentId")).toBe(
        false,
    );
    expect(
        screen.queryByRole("region", { name: "invoice-42.pdf" }),
    ).not.toBeInTheDocument();
});

test("moves the inline detail to the next selected row", async () => {
    const secondId = "33333333-3333-4333-8333-333333333333";
    const api = createApi({
        listWorkQueue: vi.fn().mockResolvedValue(
            queuePage([
                queueItem(),
                queueItem({
                    document_id: secondId,
                    original_filename: "invoice-43.pdf",
                }),
            ]),
        ),
    });

    renderPanel(api);
    const firstRow = (await screen.findByText("invoice-42.pdf")).closest("li")!;
    const secondRow = screen.getByText("invoice-43.pdf").closest("li")!;

    fireEvent.click(
        within(firstRow).getByRole("button", { name: "View details" }),
    );
    expect(firstRow).toContainElement(
        await screen.findByRole("region", { name: "invoice-42.pdf" }),
    );

    fireEvent.click(
        within(secondRow).getByRole("button", { name: "View details" }),
    );
    await waitFor(() =>
        expect(secondRow).toContainElement(
            screen.getByRole("region", { name: "invoice-42.pdf" }),
        ),
    );
    expect(
        within(firstRow).queryByRole("region", { name: "invoice-42.pdf" }),
    ).not.toBeInTheDocument();
    expect(new URL(window.location.href).searchParams.get("documentId")).toBe(
        secondId,
    );
});

test("opens a document detail from a direct URL and follows browser history", async () => {
    window.history.replaceState({}, "", `/?documentId=${documentId}`);
    const api = createApi({
        getStatus: vi.fn().mockResolvedValue(documentStatus()),
    });

    renderPanel(api);

    const details = await screen.findByRole("region", {
        name: "invoice-42.pdf",
    });
    expect(details).toBeVisible();
    expect(details.closest("li")).toBeNull();
    expect(api.getStatus).toHaveBeenCalledWith(
        documentId,
        expect.any(AbortSignal),
    );

    window.history.replaceState({}, "", "/");
    window.dispatchEvent(new PopStateEvent("popstate"));

    await waitFor(() =>
        expect(
            screen.queryByRole("region", { name: "invoice-42.pdf" }),
        ).not.toBeInTheDocument(),
    );
});

test("switches to failed work and presents bounded failure evidence", async () => {
    const failed = queueItem({
        status: "FAILED",
        processing_run_status: "FAILED",
        failure: {
            stage: "OCR_TEXT_EXTRACTION",
            code: "ACTIVITY_RETRY_EXHAUSTED",
        },
    });
    const listWorkQueue = vi
        .fn<DocumentApi["listWorkQueue"]>()
        .mockImplementation(async (queue) =>
            queue === "FAILED" ? queuePage([failed]) : queuePage([]),
        );
    const api = createApi({ listWorkQueue });

    renderPanel(api);
    fireEvent.click(await screen.findByRole("button", { name: "Failed" }));

    expect(await screen.findByText("invoice-42.pdf")).toBeVisible();
    expect(screen.getByText(/ocr text extraction/)).toBeVisible();
    expect(screen.getByText("ACTIVITY_RETRY_EXHAUSTED")).toBeVisible();
    expect(listWorkQueue).toHaveBeenCalledWith(
        "FAILED",
        0,
        expect.any(AbortSignal),
    );
});

test("lists unsupported documents in a separate queue", async () => {
    const unsupported = queueItem({
        original_filename: "unrelated.pdf",
        status: "UNSUPPORTED",
        processing_run_status: "COMPLETED",
    });
    const listWorkQueue = vi
        .fn<DocumentApi["listWorkQueue"]>()
        .mockImplementation(async (queue) =>
            queue === "UNSUPPORTED" ? queuePage([unsupported]) : queuePage([]),
        );

    renderPanel(createApi({ listWorkQueue }));
    fireEvent.click(await screen.findByRole("button", { name: "Unsupported" }));

    expect(await screen.findByText("unrelated.pdf")).toBeVisible();
    expect(listWorkQueue).toHaveBeenLastCalledWith(
        "UNSUPPORTED",
        0,
        expect.any(AbortSignal),
    );
});

test("navigates through bounded pages of a work queue", async () => {
    const firstPage = Array.from({ length: 25 }, (_, index) =>
        queueItem({
            document_id: `document-${index}`,
            original_filename: `invoice-${index}.pdf`,
        }),
    );
    const finalItem = queueItem({
        document_id: "document-25",
        original_filename: "invoice-25.pdf",
    });
    const listWorkQueue = vi
        .fn<DocumentApi["listWorkQueue"]>()
        .mockImplementation(async (_queue, offset) =>
            offset === 0
                ? queuePage(firstPage, 26)
                : queuePage([finalItem], 26),
        );

    renderPanel(createApi({ listWorkQueue }));
    expect(await screen.findByText("Page 1 of 2")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("Page 2 of 2")).toBeVisible();
    expect(screen.getByText("invoice-25.pdf")).toBeVisible();
    expect(listWorkQueue).toHaveBeenLastCalledWith(
        "ACTIVE",
        25,
        expect.any(AbortSignal),
    );
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByText("Page 1 of 2")).toBeVisible();
});

test("shows a useful empty state for a queue without documents", async () => {
    const api = createApi({
        listWorkQueue: vi.fn().mockResolvedValue(queuePage([])),
    });

    renderPanel(api);

    expect(await screen.findByText("No active documents found.")).toBeVisible();
});

test("allows retry after a queue request fails", async () => {
    const listWorkQueue = vi
        .fn<DocumentApi["listWorkQueue"]>()
        .mockRejectedValueOnce(new Error("internal database detail"))
        .mockResolvedValueOnce(queuePage([]));
    const api = createApi({ listWorkQueue });

    renderPanel(api);

    expect(
        await screen.findByText("The work queue could not be loaded."),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("No active documents found.")).toBeVisible();
});

function renderPanel(api: WorkQueueApi) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, refetchInterval: false } },
    });

    function Wrapper({ children }: PropsWithChildren) {
        return (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        );
    }

    return render(<DocumentWorkQueuesPanel api={api} />, { wrapper: Wrapper });
}

type WorkQueueApi = Pick<DocumentApi, "getStatus" | "listWorkQueue">;

function createApi(overrides: Partial<WorkQueueApi> = {}): WorkQueueApi {
    return {
        getStatus: vi.fn().mockResolvedValue(documentStatus()),
        listWorkQueue: vi.fn().mockResolvedValue(queuePage([])),
        ...overrides,
    };
}

function queueItem(
    overrides: Partial<DocumentWorkQueuePage["items"][number]> = {},
): DocumentWorkQueuePage["items"][number] {
    return {
        document_id: documentId,
        original_filename: "invoice-42.pdf",
        status: "UPLOADED",
        accepted_at: acceptedAt,
        status_changed_at: acceptedAt,
        processing_run_id: runId,
        processing_run_status: "QUEUED",
        queued_at: acceptedAt,
        started_at: null,
        attempt_count: 0,
        failure: null,
        ...overrides,
    };
}

function queuePage(
    items: DocumentWorkQueuePage["items"],
    total = items.length,
): DocumentWorkQueuePage {
    return { items, total, limit: 25, offset: 0 };
}

function documentStatus(): DocumentStatus {
    return {
        id: documentId,
        original_filename: "invoice-42.pdf",
        media_type: "application/pdf",
        size_bytes: 42_000,
        page_count: 2,
        content_sha256: "a".repeat(64),
        status: "PROCESSING",
        accepted_at: acceptedAt,
        status_changed_at: acceptedAt,
        current_run: {
            id: runId,
            previous_run_id: null,
            status: "RUNNING",
            queued_at: acceptedAt,
            started_at: acceptedAt,
            status_changed_at: acceptedAt,
            finished_at: null,
            attempt_count: 1,
            failure: null,
            processing_output: null,
            review_resolution: null,
            ai_proposal: null,
            ai_proposal_failure: null,
        },
    };
}
