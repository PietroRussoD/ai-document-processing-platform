import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Meta, StoryObj } from "@storybook/react-vite";

import type { DocumentApi, DocumentWorkQueuePage } from "../../api/documentApi";
import { DocumentWorkQueuesPanel } from "./DocumentWorkQueuesPanel";

const documentId = "11111111-1111-4111-8111-111111111111";
const runId = "22222222-2222-4222-8222-222222222222";
const timestamp = "2026-09-22T12:00:00Z";

const items: DocumentWorkQueuePage["items"] = [
    {
        document_id: documentId,
        original_filename: "supplier-invoice-1042.pdf",
        status: "PROCESSING",
        accepted_at: timestamp,
        status_changed_at: timestamp,
        processing_run_id: runId,
        processing_run_status: "RUNNING",
        queued_at: timestamp,
        started_at: timestamp,
        attempt_count: 1,
        failure: null,
    },
    {
        document_id: "33333333-3333-4333-8333-333333333333",
        original_filename: "invoice-2026-091.pdf",
        status: "UPLOADED",
        accepted_at: "2026-09-21T09:15:00Z",
        status_changed_at: "2026-09-21T09:15:00Z",
        processing_run_id: "44444444-4444-4444-8444-444444444444",
        processing_run_status: "QUEUED",
        queued_at: "2026-09-21T09:15:00Z",
        started_at: null,
        attempt_count: 0,
        failure: null,
    },
];

const api: Pick<DocumentApi, "listWorkQueue"> = {
    listWorkQueue: async () => ({
        items,
        total: items.length,
        limit: 25,
        offset: 0,
    }),
};

const meta = {
    title: "Document work queues/DocumentWorkQueuesPanel",
    component: DocumentWorkQueuesPanel,
    tags: ["autodocs"],
    parameters: { layout: "padded" },
    args: { api, selectedDocumentId: null, onSelectDocument: () => undefined },
    decorators: [
        (Story) => (
            <QueryClientProvider
                client={
                    new QueryClient({
                        defaultOptions: {
                            queries: { refetchInterval: false, retry: false },
                        },
                    })
                }
            >
                <Story />
            </QueryClientProvider>
        ),
    ],
} satisfies Meta<typeof DocumentWorkQueuesPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const ActiveQueue: Story = {};
