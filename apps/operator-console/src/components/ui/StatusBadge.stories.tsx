import type { Meta, StoryObj } from "@storybook/react-vite";

import { StatusBadge } from "./StatusBadge";

const meta = {
    title: "UI/StatusBadge",
    component: StatusBadge,
    tags: ["autodocs"],
    args: {
        label: "Processing",
        tone: "info",
    },
    argTypes: {
        tone: {
            control: "select",
            options: ["danger", "info", "neutral", "success", "warning"],
        },
    },
} satisfies Meta<typeof StatusBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Information: Story = {};

export const Success: Story = {
    args: {
        label: "Completed",
        tone: "success",
    },
};

export const Warning: Story = {
    args: {
        label: "Review required",
        tone: "warning",
    },
};

export const Danger: Story = {
    args: {
        label: "Failed",
        tone: "danger",
    },
};
