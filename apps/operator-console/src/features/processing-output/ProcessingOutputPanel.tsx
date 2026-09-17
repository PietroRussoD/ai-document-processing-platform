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

type ProcessingOutputPanelProps = {
    output: ProcessingOutput | null;
};

export function ProcessingOutputPanel({ output }: ProcessingOutputPanelProps) {
    if (output === null) {
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
                    Waiting for the first processing result.
                </p>
            </section>
        );
    }

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
                                ? "Not available"
                                : `${formatLabel(output.embedded_text.method)} · ${formatLabel(output.embedded_text.quality)}`
                        }
                    />
                    <ResultValue
                        label="OCR fallback"
                        value={
                            output.ocr_text === null
                                ? "Not used"
                                : `${formatLabel(output.ocr_text.method)} · ${output.ocr_text.character_count} characters`
                        }
                    />
                </ResultGroup>
                <ResultGroup icon={Waypoints} title="Canonical text">
                    <ResultValue
                        label="Selected source"
                        value={
                            output.selected_text === null
                                ? "Not selected"
                                : formatLabel(output.selected_text.source)
                        }
                    />
                    <ResultValue
                        label="Decision"
                        value={
                            output.selected_text === null
                                ? "Pending"
                                : formatLabel(output.selected_text.reason)
                        }
                    />
                </ResultGroup>
                <ResultGroup icon={Tags} title="Document classification">
                    {output.classification === null ? (
                        <ResultValue label="Classification" value="Pending" />
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
                <ResultGroup icon={ReceiptText} title="Invoice extraction">
                    {output.invoice_extraction === null ? (
                        <ResultValue
                            label="Extraction"
                            value={invoiceExtractionStatus(output)}
                        />
                    ) : (
                        <>
                            <ResultValue
                                label="Invoice number"
                                value={
                                    output.invoice_extraction.invoice_number ??
                                    "Not found"
                                }
                            />
                            <ResultValue
                                label="Issue date"
                                value={
                                    output.invoice_extraction.issue_date ??
                                    "Not found"
                                }
                            />
                            <ResultValue
                                label="Supplier"
                                value={
                                    output.invoice_extraction.supplier_name ??
                                    "Not found"
                                }
                            />
                            <ResultValue
                                label="Total"
                                value={formatTotal(output.invoice_extraction)}
                            />
                        </>
                    )}
                </ResultGroup>
                <ResultGroup icon={ShieldCheck} title="Invoice validation">
                    {output.invoice_validation === null ? (
                        <ResultValue
                            label="Decision"
                            value={invoiceValidationStatus(output)}
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

function invoiceExtractionStatus(output: ProcessingOutput): string {
    if (output.classification === null) {
        return "Pending";
    }
    return output.classification.document_type === "INVOICE"
        ? "Pending"
        : "Not applicable";
}

function invoiceValidationStatus(output: ProcessingOutput): string {
    if (output.classification === null) {
        return "Pending";
    }
    return output.classification.document_type === "INVOICE"
        ? "Pending"
        : "Not applicable";
}

function formatValidationIssues(issues: string[]): string {
    return issues.length === 0
        ? "No review required"
        : issues.map(formatLabel).join(", ");
}

function formatTotal(
    extraction: NonNullable<ProcessingOutput["invoice_extraction"]>,
): string {
    if (extraction.total_amount === null) {
        return "Not found";
    }
    return extraction.currency === null
        ? extraction.total_amount
        : `${extraction.currency} ${extraction.total_amount}`;
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
