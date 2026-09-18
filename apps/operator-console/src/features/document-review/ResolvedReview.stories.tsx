import type { Meta, StoryObj } from "@storybook/react-vite";

import { ResolvedReview } from "./ResolvedReview";

const meta = {
    title: "Document review/ResolvedReview",
    component: ResolvedReview,
    tags: ["autodocs"],
    parameters: {
        layout: "padded",
    },
} satisfies Meta<typeof ResolvedReview>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Approved: Story = {
    args: {
        resolution: {
            decision: "APPROVE",
            reviewer_id: "operator-42",
            review_note: "Supplier evidence verified.",
            resolved_at: "2026-09-17T18:00:00Z",
        },
    },
};

export const RejectedWithoutNote: Story = {
    args: {
        resolution: {
            decision: "REJECT",
            reviewer_id: "operator-42",
            review_note: null,
            resolved_at: "2026-09-17T18:00:00Z",
        },
    },
};
