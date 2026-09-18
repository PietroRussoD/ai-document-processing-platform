import type { Meta, StoryObj } from "@storybook/react-vite";

import { FeedbackMessage } from "./FeedbackMessage";

const meta = {
    title: "UI/FeedbackMessage",
    component: FeedbackMessage,
    tags: ["autodocs"],
    args: {
        children: "Processing requires an operator review.",
        role: "status",
        tone: "warning",
    },
    argTypes: {
        focusOnMount: {
            control: "boolean",
        },
        role: {
            control: "select",
            options: ["alert", "status"],
        },
        tone: {
            control: "select",
            options: ["danger", "info", "success", "warning"],
        },
    },
} satisfies Meta<typeof FeedbackMessage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Warning: Story = {};

export const Error: Story = {
    args: {
        children: "The persisted status could not be loaded.",
        role: "alert",
        tone: "danger",
    },
};

export const Success: Story = {
    args: {
        children: "Processing results are ready.",
        tone: "success",
    },
};
