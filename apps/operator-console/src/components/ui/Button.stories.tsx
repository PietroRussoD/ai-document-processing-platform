import { CheckCircle2, RefreshCw, Upload, XCircle } from "lucide-react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { Button } from "./Button";

const meta = {
    title: "UI/Button",
    component: Button,
    tags: ["autodocs"],
    args: {
        children: "Retry status",
        size: "md",
        variant: "secondary",
    },
    argTypes: {
        size: {
            control: "select",
            options: ["sm", "md", "lg"],
        },
        variant: {
            control: "select",
            options: ["primary", "secondary", "danger"],
        },
    },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
    args: {
        children: (
            <>
                <Upload aria-hidden="true" size={18} />
                Upload document
            </>
        ),
        size: "lg",
        variant: "primary",
    },
};

export const Secondary: Story = {
    args: {
        children: (
            <>
                <RefreshCw aria-hidden="true" size={16} />
                Retry status
            </>
        ),
        size: "sm",
    },
};

export const Danger: Story = {
    args: {
        children: (
            <>
                <XCircle aria-hidden="true" size={17} />
                Reject document
            </>
        ),
        variant: "danger",
    },
};

export const Disabled: Story = {
    args: {
        children: (
            <>
                <CheckCircle2 aria-hidden="true" size={17} />
                Approve document
            </>
        ),
        disabled: true,
        variant: "primary",
    },
};
