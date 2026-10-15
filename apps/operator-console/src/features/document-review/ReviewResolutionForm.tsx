import { CheckCircle2, CircleAlert, LoaderCircle, XCircle } from "lucide-react";
import { type ReactNode } from "react";
import { useState } from "react";

import type {
    DocumentStatus,
    ReviewResolutionRequest,
} from "../../api/documentApi";
import { Button } from "../../components/ui/Button";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";
import {
    useReviewDraft,
    type InvoiceExtraction,
    type InvoiceValues,
} from "./reviewDraft";

export type ReviewDecision = "APPROVE" | "REJECT";

type AiProposal = DocumentStatus["current_run"]["ai_proposal"];
type ReviewCorrections = ReviewResolutionRequest["corrections"];

type ReviewResolutionFormProps = {
    aiProposal?: AiProposal;
    draftKey?: string;
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
    sourcePreview?: ReactNode;
};

const reviewResolutionErrorId = "review-resolution-error";

export function ReviewResolutionForm({
    aiProposal = null,
    draftKey,
    errorMessage,
    invoiceExtraction,
    isSaving,
    onDecision,
    onOperatorTokenChange,
    onReviewNoteChange,
    operatorToken,
    reviewNote,
    sourcePreview,
}: ReviewResolutionFormProps) {
    const { draft, updateDraft } = useReviewDraft(draftKey, invoiceExtraction);
    const { invoiceValues, correctionSources } = draft;
    const [fieldErrors, setFieldErrors] = useState<InvoiceFieldErrors>({});
    const canApprove = invoiceExtraction !== null;
    const corrections = invoiceExtraction
        ? collectCorrections(
              invoiceExtraction,
              invoiceValues,
              correctionSources,
          )
        : [];

    function updateInvoiceValue(field: keyof InvoiceValues, value: string) {
        updateDraft((current) => ({
            ...current,
            invoiceValues: { ...current.invoiceValues, [field]: value },
            correctionSources: {
                ...current.correctionSources,
                [field]: "MANUAL",
            },
        }));
        setFieldErrors((current) => ({ ...current, [field]: undefined }));
    }

    function selectProposalValue(
        field: keyof InvoiceValues,
        value: string | null,
    ) {
        if (value === null) {
            return;
        }
        updateDraft((current) => ({
            ...current,
            invoiceValues: { ...current.invoiceValues, [field]: value },
            correctionSources: {
                ...current.correctionSources,
                [field]: "AI_PROPOSAL",
            },
        }));
        setFieldErrors((current) => ({ ...current, [field]: undefined }));
        document
            .getElementById(invoiceFieldId(invoiceFieldLabel(field)))
            ?.focus();
    }

    function approveDocument() {
        if (invoiceExtraction === null) {
            return;
        }

        const errors = validateInvoiceValues(invoiceExtraction, invoiceValues);
        setFieldErrors(errors);
        const firstInvalidField = Object.keys(errors)[0] as
            keyof InvoiceValues | undefined;
        if (firstInvalidField !== undefined) {
            document
                .getElementById(
                    invoiceFieldId(invoiceFieldLabel(firstInvalidField)),
                )
                ?.focus();
            return;
        }

        onDecision("APPROVE", corrections);
    }

    function restoreExtractedValue(field: keyof InvoiceValues) {
        updateDraft((current) => {
            const sources = { ...current.correctionSources };
            delete sources[field];
            return {
                ...current,
                invoiceValues: {
                    ...current.invoiceValues,
                    [field]: current.originalValues[field],
                },
                correctionSources: sources,
            };
        });
        setFieldErrors((current) => ({ ...current, [field]: undefined }));
        document
            .getElementById(invoiceFieldId(invoiceFieldLabel(field)))
            ?.focus();
    }

    return (
        <section
            className="@container mt-6 border border-amber-300 bg-amber-50 p-5"
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
                        Compare the extracted fields with the original PDF, then
                        approve or reject the document.
                    </p>
                </div>
            </div>

            <div className="mt-5 max-w-md">
                <label className="block text-sm font-medium text-app-foreground">
                    Operator token
                    <input
                        required
                        aria-describedby={
                            errorMessage !== null
                                ? `review-token-help ${reviewResolutionErrorId}`
                                : "review-token-help"
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
                <span
                    id="review-token-help"
                    className="mt-1.5 block text-sm font-normal text-app-muted"
                >
                    Use the operator token configured for this local demo to
                    view the PDF and save a decision.
                </span>
            </div>

            <div
                className={
                    sourcePreview
                        ? "mt-5 grid gap-6 @min-[48rem]:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]"
                        : "mt-5"
                }
            >
                {sourcePreview ? (
                    <div className="min-w-0">{sourcePreview}</div>
                ) : null}
                <div className="min-w-0">
                    {invoiceExtraction !== null ? (
                        <fieldset
                            className="min-w-0 border-t border-amber-200 pt-5"
                            disabled={isSaving}
                        >
                            <legend className="text-sm font-semibold text-amber-950">
                                Correct extracted invoice fields
                            </legend>
                            <p className="mt-1 text-sm text-amber-900">
                                Only changed values are recorded with this
                                approval.
                            </p>
                            {aiProposal ? (
                                <p className="mt-1 text-sm text-app-muted">
                                    AI suggestions may be wrong. Compare each
                                    value with the PDF before using it.
                                </p>
                            ) : null}
                            <div className="mt-4 grid gap-4 sm:grid-cols-2">
                                <InvoiceField
                                    error={fieldErrors.invoiceNumber}
                                    label="Invoice number"
                                    onSelectProposal={() =>
                                        selectProposalValue(
                                            "invoiceNumber",
                                            aiProposal?.invoice_number ?? null,
                                        )
                                    }
                                    onChange={(value) =>
                                        updateInvoiceValue(
                                            "invoiceNumber",
                                            value,
                                        )
                                    }
                                    originalValue={
                                        invoiceExtraction.invoice_number
                                    }
                                    proposalValue={
                                        aiProposal?.invoice_number ?? null
                                    }
                                    source={correctionSources.invoiceNumber}
                                    onReset={() =>
                                        restoreExtractedValue("invoiceNumber")
                                    }
                                    value={invoiceValues.invoiceNumber}
                                />
                                <InvoiceField
                                    error={fieldErrors.issueDate}
                                    label="Issue date"
                                    onSelectProposal={() =>
                                        selectProposalValue(
                                            "issueDate",
                                            aiProposal?.issue_date ?? null,
                                        )
                                    }
                                    onChange={(value) =>
                                        updateInvoiceValue("issueDate", value)
                                    }
                                    originalValue={invoiceExtraction.issue_date}
                                    proposalValue={
                                        aiProposal?.issue_date ?? null
                                    }
                                    source={correctionSources.issueDate}
                                    onReset={() =>
                                        restoreExtractedValue("issueDate")
                                    }
                                    type="date"
                                    value={invoiceValues.issueDate}
                                />
                                <InvoiceField
                                    error={fieldErrors.supplierName}
                                    label="Supplier"
                                    onSelectProposal={() =>
                                        selectProposalValue(
                                            "supplierName",
                                            aiProposal?.supplier_name ?? null,
                                        )
                                    }
                                    onChange={(value) =>
                                        updateInvoiceValue(
                                            "supplierName",
                                            value,
                                        )
                                    }
                                    originalValue={
                                        invoiceExtraction.supplier_name
                                    }
                                    proposalValue={
                                        aiProposal?.supplier_name ?? null
                                    }
                                    source={correctionSources.supplierName}
                                    onReset={() =>
                                        restoreExtractedValue("supplierName")
                                    }
                                    value={invoiceValues.supplierName}
                                />
                                <InvoiceField
                                    error={fieldErrors.currency}
                                    label="Currency"
                                    maxLength={3}
                                    onSelectProposal={() =>
                                        selectProposalValue(
                                            "currency",
                                            aiProposal?.currency ?? null,
                                        )
                                    }
                                    onChange={(value) =>
                                        updateInvoiceValue(
                                            "currency",
                                            value.toUpperCase(),
                                        )
                                    }
                                    originalValue={invoiceExtraction.currency}
                                    proposalValue={aiProposal?.currency ?? null}
                                    source={correctionSources.currency}
                                    onReset={() =>
                                        restoreExtractedValue("currency")
                                    }
                                    value={invoiceValues.currency}
                                />
                                <InvoiceField
                                    error={fieldErrors.totalAmount}
                                    label="Total amount"
                                    min="0.0001"
                                    onSelectProposal={() =>
                                        selectProposalValue(
                                            "totalAmount",
                                            aiProposal?.total_amount ?? null,
                                        )
                                    }
                                    onChange={(value) =>
                                        updateInvoiceValue("totalAmount", value)
                                    }
                                    originalValue={
                                        invoiceExtraction.total_amount
                                    }
                                    proposalValue={
                                        aiProposal?.total_amount ?? null
                                    }
                                    source={correctionSources.totalAmount}
                                    onReset={() =>
                                        restoreExtractedValue("totalAmount")
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

                    <label className="mt-5 block text-sm font-medium text-app-foreground">
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

                    <div className="mt-4 flex flex-wrap gap-3">
                        <Button
                            disabled={!operatorToken || isSaving || !canApprove}
                            onClick={approveDocument}
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
                </div>
            </div>
        </section>
    );
}

function InvoiceField({
    error,
    label,
    maxLength,
    min,
    onChange,
    onReset,
    onSelectProposal,
    originalValue,
    proposalValue,
    source,
    step,
    type = "text",
    value,
}: {
    error?: string;
    label: string;
    maxLength?: number;
    min?: string;
    onChange: (value: string) => void;
    onReset: () => void;
    onSelectProposal: () => void;
    originalValue: string | null;
    proposalValue: string | null;
    source?: "MANUAL" | "AI_PROPOSAL";
    step?: string;
    type?: "date" | "number" | "text";
    value: string;
}) {
    const isChanged = !sameFieldValue(value, originalValue, type);
    const hasSuggestion =
        proposalValue !== null &&
        !sameFieldValue(proposalValue, originalValue, type);
    const isSuggestionSelected =
        source === "AI_PROPOSAL" && sameFieldValue(value, proposalValue, type);
    const sourceId = `${invoiceFieldId(label)}-source`;
    const proposalId = `${invoiceFieldId(label)}-proposal`;
    return (
        <div className="min-w-0 text-sm font-medium text-app-foreground">
            <label htmlFor={invoiceFieldId(label)}>{label}</label>
            <input
                id={invoiceFieldId(label)}
                aria-describedby={[
                    sourceId,
                    hasSuggestion ? proposalId : null,
                    error ? invoiceFieldErrorId(label) : null,
                ]
                    .filter(Boolean)
                    .join(" ")}
                aria-invalid={error ? true : undefined}
                className="mt-1.5 h-10 w-full rounded border border-app-border-strong bg-app-surface px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                maxLength={maxLength}
                min={min}
                onChange={(event) => onChange(event.target.value)}
                step={step}
                type={type}
                value={value}
            />
            <p
                id={sourceId}
                aria-live="polite"
                className="mt-1.5 text-xs font-normal text-app-muted"
            >
                {isChanged
                    ? source === "AI_PROPOSAL"
                        ? "From AI suggestion"
                        : "Manual correction"
                    : originalValue === null
                      ? "Not extracted"
                      : "Extracted value"}
            </p>
            {isChanged ? (
                <div className="mt-1">
                    <p className="break-words text-xs font-normal text-app-muted">
                        Extracted value · {originalValue ?? "Not available"}
                    </p>
                    <Button
                        aria-label={`${originalValue === null ? "Clear correction" : "Restore extracted value"} for ${label}`}
                        className="mt-1"
                        onClick={onReset}
                        size="sm"
                    >
                        {originalValue === null
                            ? "Clear correction"
                            : "Restore extracted value"}
                    </Button>
                </div>
            ) : null}
            {hasSuggestion ? (
                <div className="mt-2 rounded border border-app-border bg-app-surface p-2">
                    <p id={proposalId} className="break-words font-normal">
                        <span className="block text-xs font-medium text-app-muted">
                            AI suggestion
                        </span>
                        {proposalValue}
                    </p>
                    <Button
                        aria-label={`${isSuggestionSelected ? "Suggestion selected" : "Use suggestion"} for ${label}`}
                        className="mt-2"
                        disabled={isSuggestionSelected}
                        onClick={onSelectProposal}
                        size="sm"
                    >
                        {isSuggestionSelected
                            ? "Suggestion selected"
                            : "Use suggestion"}
                    </Button>
                </div>
            ) : null}
            {error ? (
                <p
                    className="mt-1 text-sm font-normal text-red-800"
                    id={invoiceFieldErrorId(label)}
                >
                    {error}
                </p>
            ) : null}
        </div>
    );
}

function sameFieldValue(
    left: string | null,
    right: string | null,
    type: "date" | "number" | "text",
): boolean {
    return type === "number"
        ? normalizeAmount(left) === normalizeAmount(right)
        : (left ?? "").trim() === (right ?? "").trim();
}

type InvoiceFieldErrors = Partial<Record<keyof InvoiceValues, string>>;

function validateInvoiceValues(
    extraction: InvoiceExtraction,
    values: InvoiceValues,
): InvoiceFieldErrors {
    const errors: InvoiceFieldErrors = {};
    const invoiceNumber = values.invoiceNumber.trim();
    if (invoiceNumber !== extraction.invoice_number) {
        if (!invoiceNumber) {
            errors.invoiceNumber =
                "Enter a value or restore the extracted one.";
        } else if (invoiceNumber.length > 128) {
            errors.invoiceNumber = "Use no more than 128 characters.";
        }
    }

    if (values.issueDate !== (extraction.issue_date ?? "")) {
        if (!isValidDate(values.issueDate)) {
            errors.issueDate = "Enter a valid date.";
        }
    }

    const supplierName = values.supplierName.trim();
    if (supplierName !== extraction.supplier_name) {
        if (!supplierName) {
            errors.supplierName = "Enter a value or restore the extracted one.";
        } else if (supplierName.length > 512) {
            errors.supplierName = "Use no more than 512 characters.";
        }
    }

    if (values.currency !== (extraction.currency ?? "")) {
        if (!/^[A-Z]{3}$/.test(values.currency)) {
            errors.currency = "Enter a three-letter ISO 4217 currency code.";
        }
    }

    if (
        normalizeAmount(values.totalAmount) !==
        normalizeAmount(extraction.total_amount)
    ) {
        const amount = values.totalAmount.trim();
        if (!/^\d{1,16}(?:\.\d{1,4})?$/.test(amount) || Number(amount) <= 0) {
            errors.totalAmount =
                "Enter a positive amount with no more than four decimal places.";
        }
    }

    return errors;
}

function isValidDate(value: string): boolean {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) {
        return false;
    }
    const [, year, month, day] = match;
    const date = new Date(`${value}T00:00:00Z`);
    return (
        date.getUTCFullYear() === Number(year) &&
        date.getUTCMonth() + 1 === Number(month) &&
        date.getUTCDate() === Number(day)
    );
}

function collectCorrections(
    extraction: InvoiceExtraction,
    values: InvoiceValues,
    sources: Partial<Record<keyof InvoiceValues, "MANUAL" | "AI_PROPOSAL">>,
): ReviewCorrections {
    const corrections: ReviewCorrections = [];
    addTextCorrection(
        corrections,
        "INVOICE_NUMBER",
        extraction.invoice_number,
        values.invoiceNumber,
        sourceFor(sources, "invoiceNumber"),
    );
    addDateCorrection(
        corrections,
        extraction.issue_date,
        values.issueDate,
        sourceFor(sources, "issueDate"),
    );
    addTextCorrection(
        corrections,
        "SUPPLIER_NAME",
        extraction.supplier_name,
        values.supplierName,
        sourceFor(sources, "supplierName"),
    );
    addTextCorrection(
        corrections,
        "CURRENCY",
        extraction.currency,
        values.currency,
        sourceFor(sources, "currency"),
    );
    addAmountCorrection(
        corrections,
        extraction.total_amount,
        values.totalAmount,
        sourceFor(sources, "totalAmount"),
    );
    return corrections;
}

function addTextCorrection(
    corrections: ReviewCorrections,
    field: "CURRENCY" | "INVOICE_NUMBER" | "SUPPLIER_NAME",
    original: string | null,
    current: string,
    source: "MANUAL" | "AI_PROPOSAL",
) {
    const value = current.trim();
    if (value && value !== original) {
        corrections.push({ field, corrected_value: value, source });
    }
}

function addDateCorrection(
    corrections: ReviewCorrections,
    original: string | null,
    current: string,
    source: "MANUAL" | "AI_PROPOSAL",
) {
    if (current && current !== original) {
        corrections.push({
            field: "ISSUE_DATE",
            corrected_value: current,
            source,
        });
    }
}

function addAmountCorrection(
    corrections: ReviewCorrections,
    original: string | null,
    current: string,
    source: "MANUAL" | "AI_PROPOSAL",
) {
    const value = current.trim();
    if (value && normalizeAmount(value) !== normalizeAmount(original)) {
        corrections.push({
            field: "TOTAL_AMOUNT",
            corrected_value: value,
            source,
        });
    }
}

function sourceFor(
    sources: Partial<Record<keyof InvoiceValues, "MANUAL" | "AI_PROPOSAL">>,
    field: keyof InvoiceValues,
): "MANUAL" | "AI_PROPOSAL" {
    return sources[field] ?? "MANUAL";
}

function invoiceFieldId(label: string): string {
    return `invoice-field-${label.toLowerCase().replaceAll(" ", "-")}`;
}

function invoiceFieldLabel(field: keyof InvoiceValues): string {
    const labels: Record<keyof InvoiceValues, string> = {
        invoiceNumber: "Invoice number",
        issueDate: "Issue date",
        supplierName: "Supplier",
        currency: "Currency",
        totalAmount: "Total amount",
    };
    return labels[field];
}

function invoiceFieldErrorId(label: string): string {
    return `${invoiceFieldId(label)}-error`;
}

function normalizeAmount(value: string | null): string | null {
    if (!value) {
        return null;
    }
    const [whole, fraction = ""] = value.split(".");
    const normalizedFraction = fraction.replace(/0+$/, "");
    return normalizedFraction ? `${whole}.${normalizedFraction}` : whole;
}
