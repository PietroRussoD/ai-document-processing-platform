import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import type {
    DocumentApi,
    DocumentStatus,
    DocumentWorkQueuePage,
} from "../../api/documentApi";
import { DocumentsPage } from "./DocumentsPage";

const documentId = "11111111-1111-4111-8111-111111111111";
const runId = "22222222-2222-4222-8222-222222222222";
const timestamp = "2026-10-15T10:00:00Z";
type DocumentsApi = Pick<DocumentApi, "upload" | "getStatus" | "listWorkQueue">;

beforeEach(() => {
    window.history.replaceState({}, "", "/");
});

test.each(["REVIEW_REQUIRED", "APPROVED"] as const)(
    "keeps one %s detail after upload and queue selection, without nested forms or duplicate IDs",
    async (state) => {
        const status = documentStatus(state);
        const api = createApi(status);
        const { container } = renderPage(api);
        await waitFor(() => expect(api.listWorkQueue).toHaveBeenCalled());

        fireEvent.change(screen.getByLabelText("Choose a PDF"), {
            target: {
                files: [
                    new File(["synthetic pdf"], "invoice.pdf", {
                        type: "application/pdf",
                    }),
                ],
            },
        });
        fireEvent.click(
            screen.getByRole("button", { name: "Upload document" }),
        );

        const detail = await screen.findByRole("region", {
            name: "invoice.pdf",
        });
        expect(
            screen.getAllByRole("region", { name: "invoice.pdf" }),
        ).toHaveLength(1);
        expect(detail.closest("form")).toBeNull();
        expect(
            new URL(window.location.href).searchParams.get("documentId"),
        ).toBe(documentId);

        expect(
            screen.getByRole("heading", { name: "Document workspace" }),
        ).toHaveFocus();
        expect(
            screen.getByText("Browse work queues").closest("details"),
        ).not.toHaveAttribute("open");
        if (state === "REVIEW_REQUIRED") {
            openWorkQueues();
            fireEvent.click(
                screen.getByRole("button", { name: "Needs review" }),
            );
            expect(
                await screen.findByRole("button", { name: "Hide details" }),
            ).toBeVisible();
            expect(screen.getByRole("region", { name: "invoice.pdf" })).toBe(
                detail,
            );
            fireEvent.click(
                screen.getByRole("button", { name: "Hide details" }),
            );
            expect(
                screen.queryByRole("region", { name: "invoice.pdf" }),
            ).not.toBeInTheDocument();
            fireEvent.click(
                screen.getByRole("button", { name: "View details" }),
            );
            expect(
                await screen.findByRole("region", { name: "invoice.pdf" }),
            ).toBeVisible();
        }

        expect(container.querySelector("form form")).toBeNull();
        const ids = [...container.querySelectorAll("[id]")].map(
            (element) => element.id,
        );
        expect(new Set(ids).size).toBe(ids.length);
        if (state === "REVIEW_REQUIRED") {
            expect(screen.getAllByLabelText("Supplier")).toHaveLength(1);
        } else {
            expect(
                screen
                    .getByRole("button", { name: "Request reprocessing" })
                    .closest("form"),
            ).not.toBe(
                screen
                    .getByRole("button", { name: "Upload document" })
                    .closest("form"),
            );
        }
        await waitFor(() =>
            expect(
                api.listWorkQueue.mock.calls.filter(
                    ([queue]) => queue === "ACTIVE",
                ).length,
            ).toBeGreaterThan(1),
        );
    },
);

test("reopens a direct link and follows document selection through browser history", async () => {
    window.history.replaceState({}, "", `/?documentId=${documentId}`);
    const api = createApi();
    renderPage(api);

    expect(
        await screen.findByRole("region", { name: "invoice.pdf" }),
    ).toBeVisible();
    window.history.replaceState({}, "", "/");
    fireEvent(window, new PopStateEvent("popstate"));
    expect(
        screen.queryByRole("region", { name: "invoice.pdf" }),
    ).not.toBeInTheDocument();

    window.history.replaceState({}, "", `/?documentId=${documentId}`);
    fireEvent(window, new PopStateEvent("popstate"));
    expect(
        await screen.findByRole("region", { name: "invoice.pdf" }),
    ).toBeVisible();
});

test("keeps a review draft through queue pagination, filtering and refresh", async () => {
    window.history.replaceState({}, "", `/?documentId=${documentId}`);
    const reviewing = documentStatus("REVIEW_REQUIRED");
    const api = createApi(reviewing);
    const activeItems = Array.from({ length: 26 }, (_, index) =>
        queueItem(
            documentStatus(
                "PROCESSING",
                `active-${index}`,
                `active-${index}.pdf`,
            ),
        ),
    );
    let reviewItems = [queueItem(reviewing)];
    api.listWorkQueue.mockImplementation(async (queue, _token, offset = 0) => {
        const items = queue === "REVIEW" ? reviewItems : activeItems;
        return {
            items: items.slice(offset, offset + 25),
            total: items.length,
            offset,
            limit: 25,
        };
    });
    renderPage(api);
    const detail = await screen.findByRole("region", { name: "invoice.pdf" });
    fireEvent.change(screen.getByLabelText("Supplier"), {
        target: { value: "Corrected Synthetic Supplier" },
    });
    openWorkQueues();
    await screen.findByText("Page 1 of 2");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Page 2 of 2")).toBeVisible();
    expect(screen.getByLabelText("Supplier")).toHaveValue(
        "Corrected Synthetic Supplier",
    );

    openWorkQueues();
    fireEvent.click(screen.getByRole("button", { name: "Needs review" }));
    await screen.findByRole("button", { name: "Hide details" });
    openWorkQueues();
    fireEvent.click(screen.getByRole("button", { name: "Needs review" }));
    expect(screen.getByLabelText("Supplier")).toHaveValue(
        "Corrected Synthetic Supplier",
    );

    reviewItems = [];
    fireEvent.click(screen.getByRole("button", { name: "Refresh work queue" }));

    expect(
        await screen.findByText("No needs review documents found."),
    ).toBeVisible();
    expect(screen.getByRole("region", { name: "invoice.pdf" })).toBe(detail);
    expect(screen.getByLabelText("Supplier")).toHaveValue(
        "Corrected Synthetic Supplier",
    );
});

test("restores opening and closing details with browser back and forward", async () => {
    renderPage(createApi());
    fireEvent.click(
        await screen.findByRole("button", { name: "View details" }),
    );
    await screen.findByRole("region", { name: "invoice.pdf" });
    fireEvent.click(
        screen.getByRole("button", { name: "Back to work queues" }),
    );
    expect(screen.getByText("Browse work queues")).toHaveFocus();
    expect(
        screen.getByText("Browse work queues").closest("details"),
    ).toHaveAttribute("open");
    expect(
        screen.queryByRole("region", { name: "invoice.pdf" }),
    ).not.toBeInTheDocument();

    window.history.back();
    expect(
        await screen.findByRole("region", { name: "invoice.pdf" }),
    ).toBeVisible();
    window.history.forward();
    await waitFor(() =>
        expect(
            screen.queryByRole("region", { name: "invoice.pdf" }),
        ).not.toBeInTheDocument(),
    );
});

test("restores isolated review drafts through document selection and browser history", async () => {
    const second = documentStatus(
        "REVIEW_REQUIRED",
        "33333333-3333-4333-8333-333333333333",
        "invoice-2.pdf",
    );
    const first = documentStatus("REVIEW_REQUIRED");
    const api = createApi(first);
    api.listWorkQueue.mockImplementation(async (queue) => ({
        items: queue === "REVIEW" ? [queueItem(first), queueItem(second)] : [],
        total: queue === "REVIEW" ? 2 : 0,
        offset: 0,
        limit: 25,
    }));
    api.getStatus.mockImplementation(async (id) =>
        id === second.id ? second : first,
    );
    renderPage(api);
    openWorkQueues();
    fireEvent.click(screen.getByRole("button", { name: "Needs review" }));
    const firstRow = (await screen.findByText("invoice.pdf")).closest("li")!;
    fireEvent.click(
        within(firstRow).getByRole("button", { name: "View details" }),
    );
    await screen.findByRole("region", { name: "invoice.pdf" });
    fireEvent.change(screen.getByLabelText("Supplier"), {
        target: { value: "First Document Draft" },
    });
    fireEvent.change(screen.getByLabelText(/Review note/), {
        target: { value: "Verify the synthetic supplier." },
    });
    openWorkQueues();
    const secondRow = screen.getByText("invoice-2.pdf").closest("li")!;
    fireEvent.click(
        within(secondRow).getByRole("button", { name: "View details" }),
    );
    expect(
        await screen.findByRole("region", { name: "invoice-2.pdf" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Supplier")).toHaveValue("Synthetic Supplier");
    expect(screen.getByLabelText(/Review note/)).toHaveValue("");
    expect(screen.getByRole("status")).toHaveTextContent(
        "Operator token accepted.",
    );
    expect(
        screen.queryByRole("region", { name: "invoice.pdf" }),
    ).not.toBeInTheDocument();
    expect(new URL(window.location.href).searchParams.get("documentId")).toBe(
        second.id,
    );

    window.history.back();
    await screen.findByRole("region", { name: "invoice.pdf" });
    expect(screen.getByLabelText("Supplier")).toHaveValue(
        "First Document Draft",
    );
    expect(screen.getByLabelText(/Review note/)).toHaveValue(
        "Verify the synthetic supplier.",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
        "Operator token accepted.",
    );

    window.history.forward();
    await screen.findByRole("region", { name: "invoice-2.pdf" });
    expect(screen.getByLabelText("Supplier")).toHaveValue("Synthetic Supplier");
});

test("warns before leaving only while unsaved drafts exist, including hidden details", async () => {
    const reviewing = documentStatus("REVIEW_REQUIRED");
    window.history.replaceState({}, "", `/?documentId=${documentId}`);
    const { unmount } = renderPage(createApi(reviewing));
    await screen.findByRole("region", { name: "invoice.pdf" });
    expect(pageLeaveIsPrevented()).toBe(false);

    expect(pageLeaveIsPrevented()).toBe(false);
    fireEvent.change(screen.getByLabelText("Supplier"), {
        target: { value: "Corrected Supplier" },
    });
    expect(pageLeaveIsPrevented()).toBe(true);
    fireEvent.change(screen.getByLabelText("Supplier"), {
        target: { value: "Synthetic Supplier" },
    });
    expect(pageLeaveIsPrevented()).toBe(false);

    fireEvent.change(screen.getByLabelText(/Review note/), {
        target: { value: "Unfinished verification." },
    });
    expect(pageLeaveIsPrevented()).toBe(true);
    openWorkQueues();
    fireEvent.click(screen.getByRole("button", { name: "Needs review" }));
    fireEvent.click(
        await screen.findByRole("button", { name: "Hide details" }),
    );
    expect(pageLeaveIsPrevented()).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "View details" }));
    await screen.findByRole("region", { name: "invoice.pdf" });
    expect(screen.getByLabelText(/Review note/)).toHaveValue(
        "Unfinished verification.",
    );
    fireEvent.change(screen.getByLabelText(/Review note/), {
        target: { value: "" },
    });
    expect(pageLeaveIsPrevented()).toBe(false);
    fireEvent.change(screen.getByLabelText("Supplier"), {
        target: { value: "Another unsaved correction" },
    });
    expect(pageLeaveIsPrevented()).toBe(true);
    unmount();
    expect(pageLeaveIsPrevented()).toBe(false);

    renderPage(createApi(reviewing));
    await screen.findByRole("region", { name: "invoice.pdf" });
    expect(screen.getByLabelText("Supplier")).toHaveValue("Synthetic Supplier");
    expect(pageLeaveIsPrevented()).toBe(false);
});

function pageLeaveIsPrevented(): boolean {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
}

test("preserves unrelated URL parameters and the fragment when opening and closing details", async () => {
    window.history.replaceState({}, "", "/?context=demo#main-content");
    renderPage(createApi());
    fireEvent.click(
        await screen.findByRole("button", { name: "View details" }),
    );
    await screen.findByRole("region", { name: "invoice.pdf" });
    expect(window.location.search).toContain("context=demo");
    expect(window.location.hash).toBe("#main-content");

    fireEvent.click(screen.getByRole("button", { name: "Hide details" }));
    await waitFor(() => expect(window.location.search).toBe("?context=demo"));
    expect(window.location.hash).toBe("#main-content");
});

function renderPage(api: DocumentsApi) {
    const client = new QueryClient({
        defaultOptions: {
            queries: { retry: false, refetchInterval: false },
            mutations: { retry: false },
        },
    });
    const view = render(
        <QueryClientProvider client={client}>
            <DocumentsPage api={api} />
        </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "synthetic-operator-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Open documents" }));
    return view;
}

function createApi(status = documentStatus()) {
    return {
        upload: vi.fn<DocumentApi["upload"]>().mockResolvedValue({
            document_id: status.id,
            processing_run_id: runId,
            accepted_at: timestamp,
            replayed: false,
        }),
        getStatus: vi.fn<DocumentApi["getStatus"]>().mockResolvedValue(status),
        listWorkQueue: vi
            .fn<DocumentApi["listWorkQueue"]>()
            .mockImplementation(async (queue) => {
                const items =
                    (status.status === "PROCESSING" && queue === "ACTIVE") ||
                    (status.status === "REVIEW_REQUIRED" && queue === "REVIEW")
                        ? [queueItem(status)]
                        : [];
                return { items, total: items.length, offset: 0, limit: 25 };
            }),
    };
}

function queueItem(
    status: DocumentStatus,
): DocumentWorkQueuePage["items"][number] {
    return {
        document_id: status.id,
        original_filename: status.original_filename,
        status: status.status,
        accepted_at: timestamp,
        status_changed_at: timestamp,
        processing_run_id: runId,
        processing_run_status: status.current_run.status,
        queued_at: timestamp,
        started_at: timestamp,
        attempt_count: 1,
        failure: null,
    };
}

function documentStatus(
    state: "PROCESSING" | "REVIEW_REQUIRED" | "APPROVED" = "PROCESSING",
    id = documentId,
    filename = "invoice.pdf",
): DocumentStatus {
    return {
        id,
        original_filename: filename,
        media_type: "application/pdf",
        size_bytes: 100,
        page_count: 1,
        content_sha256: "a".repeat(64),
        status: state,
        accepted_at: timestamp,
        status_changed_at: timestamp,
        current_run: {
            id: runId,
            previous_run_id: null,
            status:
                state === "APPROVED"
                    ? "COMPLETED"
                    : state === "PROCESSING"
                      ? "RUNNING"
                      : "REVIEW_REQUIRED",
            queued_at: timestamp,
            started_at: timestamp,
            status_changed_at: timestamp,
            finished_at: state === "APPROVED" ? timestamp : null,
            attempt_count: 1,
            failure: null,
            review_resolution: null,
            ai_proposal: null,
            ai_proposal_failure: null,
            processing_output: {
                embedded_text: null,
                ocr_text: null,
                selected_text: null,
                classification: null,
                invoice_validation: null,
                invoice_extraction: {
                    method: "DETERMINISTIC_RULES",
                    invoice_number: "INV-DEMO-1",
                    issue_date: "2026-10-15",
                    supplier_name: "Synthetic Supplier",
                    currency: "EUR",
                    total_amount: "100.00",
                    extracted_at: timestamp,
                },
            },
        },
    };
}

function openWorkQueues() {
    const summary = screen.getByText("Browse work queues");
    if (!summary.closest("details")!.open) fireEvent.click(summary);
}
