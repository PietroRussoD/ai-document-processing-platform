import {
    ReceiptText,
    ShieldCheck,
    ScanText,
    Tags,
    Waypoints,
    type LucideIcon,
} from "lucide-react";
import { type ReactNode } from "react";

import { type DocumentStatus } from "../../api/documentApi";
import { StatusBadge } from "../../components/ui/StatusBadge";

type ProcessingOutput = NonNullable<
    DocumentStatus["current_run"]["processing_output"]
>;
type ReviewCorrections = NonNullable<
    DocumentStatus["current_run"]["review_resolution"]
>["corrections"];
type InvoiceExtraction = NonNullable<ProcessingOutput["invoice_extraction"]>;

type ProcessingOutputPanelProps = {
    corrections?: ReviewCorrections;
    output: ProcessingOutput | null;
    runStatus: DocumentStatus["current_run"]["status"];
};

export function ProcessingOutputPanel({
    corrections = [],
    output,
    runStatus,
}: ProcessingOutputPanelProps) {
    const isProcessing = ["QUEUED", "RUNNING", "WAITING_RETRY"].includes(
        runStatus,
    );
    const missingResult = isProcessing ? "Pending" : "No result recorded";
    if (
        output === null ||
        Object.values(output).every((result) => result === null)
    ) {
        return (
            <section
                className="mt-6 border-t border-app-border pt-5"
                aria-labelledby="processing-results-heading"
            >
                <h3
                    id="processing-results-heading"
                    className="text-sm font-semibold"
                >
                    Processing results
                </h3>
                <p className="mt-2 text-sm text-app-muted">
                    {isProcessing
                        ? "Waiting for the first processing result."
                        : "No processing results are recorded for this run."}
                </p>
            </section>
        );
    }

    const effectiveInvoiceExtraction = applyCorrections(
        output.invoice_extraction,
        corrections,
    );

    return (
        <section
            className="mt-6 border-t border-app-border pt-5"
            aria-labelledby="processing-results-heading"
        >
            <h3
                id="processing-results-heading"
                className="text-sm font-semibold"
            >
                Processing results
            </h3>
            <div className="mt-4 grid gap-5 md:grid-cols-2 xl:grid-cols-5">
                <ResultGroup icon={ScanText} title="Text extraction">
                    <ResultValue
                        label="Embedded text"
                        value={
                            output.embedded_text === null
                                ? missingResult
                                : `${formatLabel(output.embedded_text.method)} · ${formatLabel(output.embedded_text.quality)}`
                        }
                    />
                    <ResultValue
                        label="OCR fallback"
                        value={
                            output.ocr_text === null
                                ? "No OCR result recorded"
                                : `${formatLabel(output.ocr_text.method)} · ${output.ocr_text.character_count} characters`
                        }
                    />
                </ResultGroup>
                <ResultGroup icon={Waypoints} title="Canonical text">
                    <ResultValue
                        label="Selected source"
                        value={
                            output.selected_text === null
                                ? isProcessing
                                    ? "Not selected yet"
                                    : "No selection recorded"
                                : formatLabel(output.selected_text.source)
                        }
                    />
                    <ResultValue
                        label="Decision"
                        value={
                            output.selected_text === null
                                ? missingResult
                                : formatLabel(output.selected_text.reason)
                        }
                    />
                </ResultGroup>
                <ResultGroup icon={Tags} title="Document classification">
                    {output.classification === null ? (
                        <ResultValue
                            label="Classification"
                            value={missingResult}
                        />
                    ) : (
                        <>
                            <div>
                                <dt className="text-xs font-medium text-app-muted">
                                    Type
                                </dt>
                                <dd className="mt-1.5">
                                    <StatusBadge
                                        label={formatLabel(
                                            output.classification.document_type,
                                        )}
                                        tone={classificationTone(
                                            output.classification.document_type,
                                        )}
                                    />
                                </dd>
                            </div>
                            <ResultValue
                                label="Decision"
                                value={formatLabel(
                                    output.classification.reason,
                                )}
                            />
                        </>
                    )}
                </ResultGroup>
                <ResultGroup
                    icon={ReceiptText}
                    title={
                        corrections.length > 0
                            ? "Effective invoice values"
                            : "Invoice extraction"
                    }
                >
                    {output.invoice_extraction === null ? (
                        <ResultValue
                            label="Extraction"
                            value={invoiceStageStatus(output, missingResult)}
                        />
                    ) : (
                        <>
                            <InvoiceValue
                                label="Invoice number"
                                originalValue={
                                    output.invoice_extraction.invoice_number
                                }
                                value={
                                    effectiveInvoiceExtraction?.invoice_number ??
                                    null
                                }
                            />
                            <InvoiceValue
                                label="Issue date"
                                originalValue={
                                    output.invoice_extraction.issue_date
                                }
                                value={
                                    effectiveInvoiceExtraction?.issue_date ??
                                    null
                                }
                            />
                            <InvoiceValue
                                label="Supplier"
                                originalValue={
                                    output.invoice_extraction.supplier_name
                                }
                                value={
                                    effectiveInvoiceExtraction?.supplier_name ??
                                    null
                                }
                            />
                            <InvoiceValue
                                label="Currency"
                                originalValue={
                                    output.invoice_extraction.currency
                                }
                                value={
                                    effectiveInvoiceExtraction?.currency ?? null
                                }
                            />
                            <InvoiceValue
                                label="Total amount"
                                originalValue={formatAmount(
                                    output.invoice_extraction.total_amount,
                                    output.invoice_extraction.currency,
                                )}
                                value={formatAmount(
                                    effectiveInvoiceExtraction?.total_amount ??
                                        null,
                                    effectiveInvoiceExtraction?.currency ??
                                        null,
                                )}
                            />
                        </>
                    )}
                </ResultGroup>
                <ResultGroup
                    icon={ShieldCheck}
                    title="Original extraction validation"
                >
                    {output.invoice_validation === null ? (
                        <ResultValue
                            label="Decision"
                            value={invoiceStageStatus(output, missingResult)}
                        />
                    ) : (
                        <>
                            <div>
                                <dt className="text-xs font-medium text-app-muted">
                                    Decision
                                </dt>
                                <dd className="mt-1.5">
                                    <StatusBadge
                                        label={formatLabel(
                                            output.invoice_validation.decision,
                                        )}
                                        tone={
                                            output.invoice_validation
                                                .decision === "AUTO_APPROVE"
                                                ? "success"
                                                : "warning"
                                        }
                                    />
                                </dd>
                            </div>
                            <ResultValue
                                label="Review reasons"
                                value={formatValidationIssues(
                                    output.invoice_validation.issues,
                                )}
                            />
                        </>
                    )}
                </ResultGroup>
            </div>
        </section>
    );
}

function invoiceStageStatus(
    output: ProcessingOutput,
    missingResult: string,
): string {
    return output.classification !== null &&
        output.classification.document_type !== "INVOICE"
        ? "Not applicable"
        : missingResult;
}

function formatValidationIssues(issues: string[]): string {
    return issues.length === 0
        ? "No review required"
        : issues.map(formatLabel).join(", ");
}

function formatAmount(
    amount: string | null,
    currency: string | null,
): string | null {
    if (amount === null) {
        return null;
    }
    return currency === null ? amount : `${currency} ${amount}`;
}

function InvoiceValue({
    label,
    originalValue,
    value,
}: {
    label: string;
    originalValue: string | null;
    value: string | null;
}) {
    const changed = value !== originalValue;
    return (
        <div>
            <dt className="text-xs font-medium text-app-muted">{label}</dt>
            <dd className="mt-1 break-words">
                {value ?? "Not found"}
                {changed ? (
                    <span className="ml-2 align-middle">
                        <StatusBadge label="Corrected" tone="info" />
                    </span>
                ) : null}
            </dd>
            {changed ? (
                <p className="mt-1 text-xs text-app-muted">
                    Extracted: {originalValue ?? "Not found"}
                </p>
            ) : null}
        </div>
    );
}

function applyCorrections(
    extraction: InvoiceExtraction | null,
    corrections: ReviewCorrections,
): InvoiceExtraction | null {
    if (extraction === null || corrections.length === 0) {
        return extraction;
    }
    const values = new Map(
        corrections.map((correction) => [
            correction.field,
            correction.corrected_value,
        ]),
    );
    return {
        ...extraction,
        invoice_number:
            values.get("INVOICE_NUMBER") ?? extraction.invoice_number,
        issue_date: values.get("ISSUE_DATE") ?? extraction.issue_date,
        supplier_name: values.get("SUPPLIER_NAME") ?? extraction.supplier_name,
        currency: values.get("CURRENCY") ?? extraction.currency,
        total_amount: values.get("TOTAL_AMOUNT") ?? extraction.total_amount,
    };
}

function ResultGroup({
    children,
    icon: Icon,
    title,
}: {
    children: ReactNode;
    icon: LucideIcon;
    title: string;
}) {
    return (
        <div>
            <div className="flex items-center gap-2 text-sm font-medium">
                <Icon
                    aria-hidden="true"
                    size={16}
                    className="text-app-accent"
                />
                <h4>{title}</h4>
            </div>
            <dl className="mt-3 space-y-3 text-sm">{children}</dl>
        </div>
    );
}

function ResultValue({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <dt className="text-xs font-medium text-app-muted">{label}</dt>
            <dd className="mt-1 break-words">{value}</dd>
        </div>
    );
}

function formatLabel(value: string): string {
    const knownLabels: Record<string, string> = {
        OCR: "OCR",
        OCR_HAS_MORE_TEXT: "OCR has more text",
        OCR_RECOMMENDED: "OCR recommended",
        PYMUPDF: "PyMuPDF",
        TESSERACT: "Tesseract",
    };
    if (value in knownLabels) {
        return knownLabels[value];
    }
    return value
        .toLowerCase()
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function classificationTone(
    documentType: NonNullable<
        ProcessingOutput["classification"]
    >["document_type"],
): Parameters<typeof StatusBadge>[0]["tone"] {
    return documentType === "UNKNOWN" ? "warning" : "success";
}
