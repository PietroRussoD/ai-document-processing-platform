import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { type DocumentApi } from "../../api/documentApi";
import { ReviewResolutionForm } from "./ReviewResolutionForm";
import { SourcePdfPreview } from "./SourcePdfPreview";

type StoryArgs = {
    errorMessage: string | null;
    hasExtraction: boolean;
    hasAiProposal: boolean;
    isSaving: boolean;
    sourceState: "none" | "available" | "loading" | "failed";
};

const meta = {
    title: "Document review/ReviewResolutionForm",
    component: InteractiveReviewResolutionForm,
    tags: ["autodocs"],
    args: {
        errorMessage: null,
        hasExtraction: true,
        hasAiProposal: false,
        isSaving: false,
        sourceState: "none",
    },
    argTypes: {
        hasExtraction: { control: "boolean" },
        hasAiProposal: { control: "boolean" },
        errorMessage: {
            control: "text",
        },
        isSaving: {
            control: "boolean",
        },
        sourceState: {
            control: "select",
            options: ["none", "available", "loading", "failed"],
        },
    },
    parameters: { layout: "padded" },
} satisfies Meta<typeof InteractiveReviewResolutionForm>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {};

export const MissingExtraction: Story = { args: { hasExtraction: false } };

export const Saving: Story = {
    args: {
        isSaving: true,
    },
};

export const AuthenticationRejected: Story = {
    args: {
        errorMessage: "Review authentication was rejected.",
    },
};

export const WithSourcePdf: Story = { args: { sourceState: "available" } };
export const WithAiSuggestions: Story = {
    args: { hasAiProposal: true, sourceState: "available" },
};
export const LoadingSourcePdf: Story = { args: { sourceState: "loading" } };
export const SourcePdfFailure: Story = { args: { sourceState: "failed" } };

function InteractiveReviewResolutionForm({
    errorMessage,
    hasExtraction,
    hasAiProposal,
    isSaving,
    sourceState,
}: StoryArgs) {
    const [operatorToken, setOperatorToken] = useState("");
    const [reviewNote, setReviewNote] = useState("");

    return (
        <ReviewResolutionForm
            aiProposal={
                hasAiProposal
                    ? {
                          schema_version: 1,
                          provider: "OLLAMA",
                          model_reference: "synthetic-demo-model",
                          model_digest: null,
                          prompt_version: "invoice-v1",
                          selected_text_sha256: "a".repeat(64),
                          status: "VALID",
                          invoice_number: "DEMO-INV-1001",
                          issue_date: "2026-09-15",
                          supplier_name: "Northstar Office Supplies",
                          currency: "EUR",
                          total_amount: "1275.00",
                          issues: [],
                          proposed_at: "2026-09-29T12:00:06Z",
                      }
                    : null
            }
            errorMessage={errorMessage}
            invoiceExtraction={
                !hasExtraction
                    ? null
                    : {
                          method: "DETERMINISTIC_RULES",
                          invoice_number: "DEMO-INV-1001",
                          issue_date: "2026-09-15",
                          supplier_name: "Northstar Office Supplies Ltd",
                          currency: null,
                          total_amount: null,
                          extracted_at: "2026-09-29T12:00:05Z",
                      }
            }
            isSaving={isSaving}
            onDecision={() => undefined}
            onOperatorTokenChange={setOperatorToken}
            onReviewNoteChange={setReviewNote}
            operatorToken={operatorToken}
            reviewNote={reviewNote}
            sourcePreview={
                sourceState === "none" ? undefined : (
                    <SourcePdfPreview
                        api={previewApi(sourceState)}
                        documentId="storybook-invoice"
                        operatorToken={operatorToken}
                    />
                )
            }
        />
    );
}

function previewApi(
    state: StoryArgs["sourceState"],
): Pick<DocumentApi, "getSourceDocument"> {
    return {
        getSourceDocument: async (_id, _token, signal) => {
            if (state === "failed")
                throw new Error("Synthetic source loading failure");
            if (state === "loading") {
                return new Promise<Blob>((_resolve, reject) => {
                    signal?.addEventListener(
                        "abort",
                        () => reject(new DOMException("Aborted", "AbortError")),
                        { once: true },
                    );
                });
            }
            const response = await fetch("/fixtures/invoice-digital.pdf", {
                signal,
            });
            if (!response.ok) throw new Error("Synthetic fixture unavailable");
            return response.blob();
        },
    };
}
