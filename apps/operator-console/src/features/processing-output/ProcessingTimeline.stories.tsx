import type { Meta, StoryObj } from "@storybook/react-vite";

import { type DocumentStatus } from "../../api/documentApi";
import { ProcessingTimeline } from "./ProcessingTimeline";

const meta = {
    title: "Processing output/ProcessingTimeline",
    component: ProcessingTimeline,
    tags: ["autodocs"],
    parameters: { layout: "padded" },
} satisfies Meta<typeof ProcessingTimeline>;

export default meta;
type Story = StoryObj<typeof meta>;

const run: DocumentStatus["current_run"] = {
    id: "run-42",
    previous_run_id: null,
    status: "REVIEW_REQUIRED",
    queued_at: "2026-09-29T12:00:00Z",
    started_at: "2026-09-29T12:00:01Z",
    status_changed_at: "2026-09-29T12:00:05Z",
    finished_at: null,
    attempt_count: 1,
    failure: null,
    review_resolution: null,
    ai_proposal: null,
    ai_proposal_failure: null,
    processing_output: {
        embedded_text: {
            method: "PYMUPDF",
            quality: "SUFFICIENT",
            page_count: 1,
            character_count: 150,
            non_whitespace_character_count: 120,
            extracted_at: "2026-09-29T12:00:02Z",
        },
        ocr_text: null,
        selected_text: {
            source: "EMBEDDED",
            reason: "EMBEDDED_SUFFICIENT",
            selected_at: "2026-09-29T12:00:03Z",
        },
        classification: {
            document_type: "INVOICE",
            reason: "KEYWORD_MATCHED",
            classified_at: "2026-09-29T12:00:04Z",
        },
        invoice_extraction: {
            method: "DETERMINISTIC_RULES",
            invoice_number: "INV-42",
            issue_date: "2026-09-29",
            supplier_name: "Acme Ltd",
            currency: null,
            total_amount: null,
            extracted_at: "2026-09-29T12:00:05Z",
        },
        invoice_validation: {
            decision: "REVIEW_REQUIRED",
            issues: ["MISSING_CURRENCY", "MISSING_TOTAL_AMOUNT"],
            validated_at: "2026-09-29T12:00:05Z",
        },
    },
};

export const Running: Story = {
    args: { run },
    render: (args) => {
        const at = new Date().toISOString();
        return (
            <ProcessingTimeline
                run={{
                    ...args.run,
                    ai_execution: {
                        status: "RUNNING",
                        started_at: at,
                        finished_at: null,
                        status_changed_at: at,
                    },
                }}
            />
        );
    },
};

export const Disabled: Story = {
    args: {
        run: {
            ...run,
            ai_execution: {
                status: "DISABLED",
                started_at: null,
                finished_at: "2026-09-29T12:00:06Z",
                status_changed_at: "2026-09-29T12:00:06Z",
            },
        },
    },
};

export const Failed: Story = {
    args: {
        run: {
            ...run,
            ai_execution: {
                status: "FAILED",
                started_at: "2026-09-29T12:00:05Z",
                finished_at: "2026-09-29T12:00:06Z",
                status_changed_at: "2026-09-29T12:00:06Z",
            },
        },
    },
};

export const Unrecorded: Story = { args: { run } };

export const StaleRunning: Story = {
    args: {
        run: {
            ...run,
            ai_execution: {
                status: "RUNNING",
                started_at: "2026-09-16T12:00:04Z",
                finished_at: null,
                status_changed_at: "2026-09-16T12:00:04Z",
            },
        },
    },
};
