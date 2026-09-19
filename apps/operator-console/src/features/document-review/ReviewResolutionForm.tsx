import { CheckCircle2, CircleAlert, LoaderCircle, XCircle } from "lucide-react";
import { useState } from "react";

import type {
    DocumentStatus,
    ReviewResolutionRequest,
} from "../../api/documentApi";
import { Button } from "../../components/ui/Button";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";

export type ReviewDecision = "APPROVE" | "REJECT";

type InvoiceExtraction = NonNullable<
    NonNullable<
        DocumentStatus["current_run"]["processing_output"]
    >["invoice_extraction"]
>;
type ReviewCorrections = ReviewResolutionRequest["corrections"];
type InvoiceValues = {
    invoiceNumber: string;
    issueDate: string;
    supplierName: string;
    currency: string;
    totalAmount: string;
};

type ReviewResolutionFormProps = {
    errorMessage: string | null;
    invoiceExtraction: InvoiceExtraction | null;
    isSaving: boolean;
    onDecision: (
        decision: ReviewDecision,
        corrections: ReviewCorrections,
    ) => void;
    onOperatorTokenChange: (operatorToken: string) => void;
    onReviewNoteChange: (reviewNote: string) => void;
    operatorToken: string;
    reviewNote: string;
};

const reviewResolutionErrorId = "review-resolution-error";

export function ReviewResolutionForm({
    errorMessage,
    invoiceExtraction,
    isSaving,
    onDecision,
    onOperatorTokenChange,
    onReviewNoteChange,
    operatorToken,
    reviewNote,
}: ReviewResolutionFormProps) {
    const [invoiceValues, setInvoiceValues] = useState(() =>
        toInvoiceValues(invoiceExtraction),
    );
    const canApprove = invoiceExtraction !== null;
    const corrections = invoiceExtraction
        ? collectCorrections(invoiceExtraction, invoiceValues)
        : [];

    function updateInvoiceValue(field: keyof InvoiceValues, value: string) {
        setInvoiceValues((current) => ({ ...current, [field]: value }));
    }

    return (
        <section
            className="mt-6 border border-amber-300 bg-amber-50 p-5"
            aria-labelledby="review-resolution-heading"
        >
            <div className="flex items-start gap-3">
                <CircleAlert
                    aria-hidden="true"
                    className="mt-0.5 shrink-0 text-amber-800"
                    size={20}
                />
                <div>
                    <h3
                        id="review-resolution-heading"
                        className="text-sm font-semibold text-amber-950"
                    >
                        Resolve operator review
                    </h3>
                    <p className="mt-1 text-sm text-amber-900">
                        Approve or reject the document after checking the
                        persisted processing results.
                    </p>
                </div>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium text-app-foreground">
                    Operator token
                    <input
                        required
                        aria-describedby={
                            errorMessage !== null
                                ? reviewResolutionErrorId
                                : undefined
                        }
                        autoComplete="off"
                        className="mt-1.5 h-10 w-full rounded border border-app-border-strong bg-app-surface px-3 font-mono text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        disabled={isSaving}
                        onChange={(event) =>
                            onOperatorTokenChange(event.target.value)
                        }
                        spellCheck={false}
                        type="password"
                        value={operatorToken}
                    />
                </label>
                <label className="block text-sm font-medium text-app-foreground">
                    Review note{" "}
                    <span className="font-normal text-app-muted">
                        (optional)
                    </span>
                    <textarea
                        className="mt-1.5 min-h-20 w-full resize-y rounded border border-app-border-strong bg-app-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        disabled={isSaving}
                        maxLength={2000}
                        onChange={(event) =>
                            onReviewNoteChange(event.target.value)
                        }
                        value={reviewNote}
                    />
                </label>
            </div>

            {invoiceExtraction !== null ? (
                <fieldset className="mt-5 border-t border-amber-200 pt-5">
                    <legend className="text-sm font-semibold text-amber-950">
                        Correct extracted invoice fields
                    </legend>
                    <p className="mt-1 text-sm text-amber-900">
                        Only changed values are recorded with this approval.
                    </p>
                    <div className="mt-4 grid gap-4 sm:grid-cols-2">
                        <InvoiceField
                            label="Invoice number"
                            onChange={(value) =>
                                updateInvoiceValue("invoiceNumber", value)
                            }
                            value={invoiceValues.invoiceNumber}
                        />
                        <InvoiceField
                            label="Issue date"
                            onChange={(value) =>
                                updateInvoiceValue("issueDate", value)
                            }
                            type="date"
                            value={invoiceValues.issueDate}
                        />
                        <InvoiceField
                            label="Supplier"
                            onChange={(value) =>
                                updateInvoiceValue("supplierName", value)
                            }
                            value={invoiceValues.supplierName}
                        />
                        <InvoiceField
                            label="Currency"
                            maxLength={3}
                            onChange={(value) =>
                                updateInvoiceValue(
                                    "currency",
                                    value.toUpperCase(),
                                )
                            }
                            value={invoiceValues.currency}
                        />
                        <InvoiceField
                            label="Total amount"
                            min="0.0001"
                            onChange={(value) =>
                                updateInvoiceValue("totalAmount", value)
                            }
                            step="0.0001"
                            type="number"
                            value={invoiceValues.totalAmount}
                        />
                    </div>
                </fieldset>
            ) : (
                <FeedbackMessage className="mt-5" tone="warning">
                    An invoice extraction is required before approval.
                </FeedbackMessage>
            )}

            <div className="mt-4 flex flex-wrap gap-3">
                <Button
                    disabled={!operatorToken || isSaving || !canApprove}
                    onClick={() => onDecision("APPROVE", corrections)}
                    variant="primary"
                >
                    {isSaving ? (
                        <LoaderCircle
                            aria-hidden="true"
                            className="motion-safe:animate-spin"
                            size={17}
                        />
                    ) : (
                        <CheckCircle2 aria-hidden="true" size={17} />
                    )}
                    Approve document
                </Button>
                <Button
                    disabled={!operatorToken || isSaving}
                    onClick={() => onDecision("REJECT", [])}
                    variant="danger"
                >
                    <XCircle aria-hidden="true" size={17} />
                    Reject document
                </Button>
            </div>

            <div>
                {isSaving ? (
                    <FeedbackMessage className="mt-4" tone="info">
                        Saving review decision
                    </FeedbackMessage>
                ) : null}
                {errorMessage !== null ? (
                    <FeedbackMessage
                        id={reviewResolutionErrorId}
                        className="mt-4"
                        focusOnMount
                        role="alert"
                        tone="danger"
                    >
                        {errorMessage}
                    </FeedbackMessage>
                ) : null}
            </div>
        </section>
    );
}

function InvoiceField({
    label,
    maxLength,
    min,
    onChange,
    step,
    type = "text",
    value,
}: {
    label: string;
    maxLength?: number;
    min?: string;
    onChange: (value: string) => void;
    step?: string;
    type?: "date" | "number" | "text";
    value: string;
}) {
    return (
        <label className="block text-sm font-medium text-app-foreground">
            {label}
            <input
                className="mt-1.5 h-10 w-full rounded border border-app-border-strong bg-app-surface px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                maxLength={maxLength}
                min={min}
                onChange={(event) => onChange(event.target.value)}
                step={step}
                type={type}
                value={value}
            />
        </label>
    );
}

function toInvoiceValues(extraction: InvoiceExtraction | null): InvoiceValues {
    return {
        invoiceNumber: extraction?.invoice_number ?? "",
        issueDate: extraction?.issue_date ?? "",
        supplierName: extraction?.supplier_name ?? "",
        currency: extraction?.currency ?? "",
        totalAmount: extraction?.total_amount ?? "",
    };
}

function collectCorrections(
    extraction: InvoiceExtraction,
    values: InvoiceValues,
): ReviewCorrections {
    const corrections: ReviewCorrections = [];
    addTextCorrection(
        corrections,
        "INVOICE_NUMBER",
        extraction.invoice_number,
        values.invoiceNumber,
    );
    addDateCorrection(corrections, extraction.issue_date, values.issueDate);
    addTextCorrection(
        corrections,
        "SUPPLIER_NAME",
        extraction.supplier_name,
        values.supplierName,
    );
    addTextCorrection(
        corrections,
        "CURRENCY",
        extraction.currency,
        values.currency,
    );
    addAmountCorrection(
        corrections,
        extraction.total_amount,
        values.totalAmount,
    );
    return corrections;
}

function addTextCorrection(
    corrections: ReviewCorrections,
    field: "CURRENCY" | "INVOICE_NUMBER" | "SUPPLIER_NAME",
    original: string | null,
    current: string,
) {
    const value = current.trim();
    if (value && value !== original) {
        corrections.push({ field, corrected_value: value });
    }
}

function addDateCorrection(
    corrections: ReviewCorrections,
    original: string | null,
    current: string,
) {
    if (current && current !== original) {
        corrections.push({ field: "ISSUE_DATE", corrected_value: current });
    }
}

function addAmountCorrection(
    corrections: ReviewCorrections,
    original: string | null,
    current: string,
) {
    const value = current.trim();
    if (value && normalizeAmount(value) !== normalizeAmount(original)) {
        corrections.push({ field: "TOTAL_AMOUNT", corrected_value: value });
    }
}

function normalizeAmount(value: string | null): string | null {
    if (!value) {
        return null;
    }
    const [whole, fraction = ""] = value.split(".");
    const normalizedFraction = fraction.replace(/0+$/, "");
    return normalizedFraction ? `${whole}.${normalizedFraction}` : whole;
}
