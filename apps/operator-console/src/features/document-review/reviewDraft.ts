import {
    createContext,
    useContext,
    useState,
    type Dispatch,
    type SetStateAction,
} from "react";

import type { DocumentStatus } from "../../api/documentApi";

export type InvoiceExtraction = NonNullable<
    NonNullable<
        DocumentStatus["current_run"]["processing_output"]
    >["invoice_extraction"]
>;
export type InvoiceValues = {
    invoiceNumber: string;
    issueDate: string;
    supplierName: string;
    currency: string;
    totalAmount: string;
};
type CorrectionSources = Partial<
    Record<keyof InvoiceValues, "MANUAL" | "AI_PROPOSAL">
>;
export type ReviewDraft = {
    invoiceValues: InvoiceValues;
    originalValues: InvoiceValues;
    correctionSources: CorrectionSources;
    reviewNote: string;
};
export type ReviewDrafts = Partial<Record<string, ReviewDraft>>;

export const ReviewDraftContext = createContext<{
    drafts: ReviewDrafts;
    setDrafts: Dispatch<SetStateAction<ReviewDrafts>>;
} | null>(null);

export function useReviewDraft(
    key: string | undefined,
    extraction: InvoiceExtraction | null,
) {
    const store = useContext(ReviewDraftContext);
    const [localDraft, setLocalDraft] = useState(() =>
        createReviewDraft(extraction),
    );
    const draft =
        store && key
            ? (store.drafts[key] ?? createReviewDraft(extraction))
            : localDraft;

    function updateDraft(update: (current: ReviewDraft) => ReviewDraft) {
        if (store && key) {
            store.setDrafts((current) => ({
                ...current,
                [key]: update(current[key] ?? createReviewDraft(extraction)),
            }));
        } else {
            setLocalDraft(update);
        }
    }

    function clearDraft() {
        if (store && key) {
            store.setDrafts((current) => {
                const next = { ...current };
                delete next[key];
                return next;
            });
        } else {
            setLocalDraft(createReviewDraft(extraction));
        }
    }

    return { draft, updateDraft, clearDraft };
}

export function hasUnsavedReviewDraft(draft: ReviewDraft): boolean {
    return (
        draft.reviewNote.trim() !== "" ||
        (Object.keys(draft.invoiceValues) as (keyof InvoiceValues)[]).some(
            (field) =>
                draft.invoiceValues[field] !== draft.originalValues[field],
        )
    );
}

function createReviewDraft(extraction: InvoiceExtraction | null): ReviewDraft {
    const values = {
        invoiceNumber: extraction?.invoice_number ?? "",
        issueDate: extraction?.issue_date ?? "",
        supplierName: extraction?.supplier_name ?? "",
        currency: extraction?.currency ?? "",
        totalAmount: extraction?.total_amount ?? "",
    };
    return {
        invoiceValues: values,
        originalValues: values,
        correctionSources: {},
        reviewNote: "",
    };
}
