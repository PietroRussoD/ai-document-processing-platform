import type { Meta, StoryObj } from "@storybook/react-vite";

import { AiInvoiceComparison } from "./AiInvoiceComparison";

const meta = {
    title: "Processing output/AiInvoiceComparison",
    component: AiInvoiceComparison,
    tags: ["autodocs"],
    parameters: { layout: "padded" },
} satisfies Meta<typeof AiInvoiceComparison>;

export default meta;
type Story = StoryObj<typeof meta>;

const extraction = {
    method: "DETERMINISTIC_RULES" as const,
    invoice_number: "INV-42",
    issue_date: "2026-09-16",
    supplier_name: "Acme Ltd",
    currency: "EUR",
    total_amount: "12.50",
    extracted_at: "2026-09-16T12:00:04Z",
};

export const PartialProposal: Story = {
    args: {
        extraction,
        proposal: {
            schema_version: 1,
            provider: "OLLAMA",
            model_reference: "qwen3:8b",
            model_digest: null,
            prompt_version: "invoice-v1",
            selected_text_sha256: "a".repeat(64),
            status: "PARTIAL",
            invoice_number: "INV-42",
            issue_date: null,
            supplier_name: "Acme Europe Ltd",
            currency: "EUR",
            total_amount: "12.50",
            issues: [{ code: "MISSING_FIELD", field: "ISSUE_DATE" }],
            proposed_at: "2026-09-16T12:00:06Z",
        },
        failure: null,
        execution: {
            status: "COMPLETED",
            started_at: "2026-09-16T12:00:04Z",
            finished_at: "2026-09-16T12:00:06Z",
            status_changed_at: "2026-09-16T12:00:06Z",
        },
    },
};

export const ProviderTimeout: Story = {
    args: {
        extraction,
        proposal: null,
        failure: {
            provider: "OLLAMA",
            model_reference: "qwen3:8b",
            code: "TIMEOUT",
            failed_at: "2026-09-16T12:00:06Z",
        },
        execution: {
            status: "FAILED",
            started_at: "2026-09-16T12:00:04Z",
            finished_at: "2026-09-16T12:00:06Z",
            status_changed_at: "2026-09-16T12:00:06Z",
        },
    },
};

export const Running: Story = {
    args: { extraction, proposal: null, failure: null },
    render: (args) => {
        const at = new Date().toISOString();
        return (
            <AiInvoiceComparison
                {...args}
                execution={{
                    status: "RUNNING",
                    started_at: at,
                    finished_at: null,
                    status_changed_at: at,
                }}
            />
        );
    },
};

export const Disabled: Story = {
    args: {
        extraction,
        proposal: null,
        failure: null,
        execution: {
            status: "DISABLED",
            started_at: null,
            finished_at: "2026-09-29T10:00:00Z",
            status_changed_at: "2026-09-29T10:00:00Z",
        },
    },
};

export const Unrecorded: Story = {
    args: {
        extraction,
        proposal: null,
        failure: null,
        execution: null,
        applicable: true,
    },
};

export const StaleRunning: Story = {
    args: {
        extraction,
        proposal: null,
        failure: null,
        execution: {
            status: "RUNNING",
            started_at: "2026-09-16T12:00:04Z",
            finished_at: null,
            status_changed_at: "2026-09-16T12:00:04Z",
        },
    },
};
