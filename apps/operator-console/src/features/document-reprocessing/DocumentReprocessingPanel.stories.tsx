import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { DocumentReprocessingPanel } from "./DocumentReprocessingPanel";

const meta = {
    title: "Document reprocessing/DocumentReprocessingPanel",
    component: DocumentReprocessingPanel,
    tags: ["autodocs"],
    parameters: {
        layout: "padded",
    },
    decorators: [
        (Story) => (
            <QueryClientProvider
                client={
                    new QueryClient({
                        defaultOptions: { mutations: { retry: false } },
                    })
                }
            >
                <Story />
            </QueryClientProvider>
        ),
    ],
} satisfies Meta<typeof DocumentReprocessingPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {
    args: {
        documentId: "11111111-1111-4111-8111-111111111111",
        run: {
            id: "22222222-2222-4222-8222-222222222222",
            previous_run_id: "33333333-3333-4333-8333-333333333333",
            status: "COMPLETED",
            queued_at: "2026-09-20T11:00:00Z",
            started_at: "2026-09-20T11:00:01Z",
            status_changed_at: "2026-09-20T11:00:02Z",
            finished_at: "2026-09-20T11:00:02Z",
            attempt_count: 1,
            failure: null,
            processing_output: null,
            review_resolution: null,
            ai_proposal: null,
            ai_proposal_failure: null,
        },
    },
};
