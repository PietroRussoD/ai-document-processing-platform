import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import {
    createDocumentApi,
    type DocumentApi,
    type DocumentStatus,
} from "../../api/documentApi";
import { Button } from "../../components/ui/Button";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { ProcessingOutputPanel } from "../processing-output/ProcessingOutputPanel";
import { AiInvoiceComparison } from "../processing-output/AiInvoiceComparison";
import { ProcessingTimeline } from "../processing-output/ProcessingTimeline";
import { ReviewResolutionPanel } from "../document-review/ReviewResolutionPanel";
import { DocumentReprocessingPanel } from "../document-reprocessing/DocumentReprocessingPanel";
import { statusPollInterval } from "./statusPolling";

type StatusApi = Pick<DocumentApi, "getStatus">;
type VisibleStatus =
    DocumentStatus["status"] | DocumentStatus["current_run"]["status"];
type StatusTone = Parameters<typeof StatusBadge>[0]["tone"];

type DocumentStatusPanelProps = {
    api?: StatusApi;
    documentId: string;
};

const defaultApi = createDocumentApi();

export function DocumentStatusPanel({
    api = defaultApi,
    documentId,
}: DocumentStatusPanelProps) {
    const statusQuery = useQuery({
        queryKey: ["document-status", documentId],
        queryFn: ({ signal }) => api.getStatus(documentId, signal),
        refetchInterval: (query) =>
            statusPollInterval(query.state.data?.current_run),
    });

    if (statusQuery.isPending) {
        return (
            <section className="mt-4 border border-app-border bg-app-surface p-5">
                <h3 className="text-sm font-semibold">Document details</h3>
                <FeedbackMessage className="mt-3" tone="info">
                    Loading document details
                </FeedbackMessage>
            </section>
        );
    }

    if (statusQuery.isError) {
        return (
            <section className="mt-4 border border-app-border bg-app-surface p-5">
                <h3 className="text-sm font-semibold">Document details</h3>
                <FeedbackMessage className="mt-3" role="alert" tone="danger">
                    The document details could not be loaded. Check your
                    connection and try again.
                </FeedbackMessage>
                <Button
                    className="mt-4"
                    onClick={() => void statusQuery.refetch()}
                    size="sm"
                >
                    <RefreshCw aria-hidden="true" size={16} />
                    Retry loading
                </Button>
            </section>
        );
    }

    const document = statusQuery.data;
    const guidance = documentGuidance(document);
    const reviewReasons =
        document.status === "REVIEW_REQUIRED"
            ? (document.current_run.processing_output?.invoice_validation
                  ?.issues ?? [])
            : [];
    const showProgress =
        ["QUEUED", "RUNNING", "WAITING_RETRY"].includes(
            document.current_run.status,
        ) || document.current_run.ai_execution?.status === "RUNNING";
    return (
        <section
            aria-labelledby="document-status-heading"
            className="mt-4 border border-app-border bg-app-surface p-4 sm:p-5"
        >
            <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                    <h3
                        className="break-words text-base font-semibold"
                        id="document-status-heading"
                    >
                        {statusQuery.data.original_filename}
                    </h3>
                    <div className="mt-2 flex flex-wrap gap-2">
                        <div className="flex items-center gap-1.5">
                            <span className="text-xs text-app-muted">
                                Document status
                            </span>
                            <StatusBadge
                                label={formatStatus(statusQuery.data.status)}
                                tone={statusTone(statusQuery.data.status)}
                            />
                        </div>
                        <div className="flex items-center gap-1.5">
                            <span className="text-xs text-app-muted">
                                Processing status
                            </span>
                            <StatusBadge
                                label={formatStatus(
                                    statusQuery.data.current_run.status,
                                )}
                                tone={statusTone(
                                    statusQuery.data.current_run.status,
                                )}
                            />
                        </div>
                    </div>
                </div>
                <Button
                    aria-label="Refresh document status"
                    title="Refresh document status"
                    className="w-9 !px-0"
                    disabled={statusQuery.isFetching}
                    onClick={() => void statusQuery.refetch()}
                    size="sm"
                >
                    <RefreshCw aria-hidden="true" size={16} />
                </Button>
            </div>
            <FeedbackMessage className="mt-4" tone={guidance.tone}>
                <p className="font-semibold">{guidance.title}</p>
                <p className="mt-1">{guidance.description}</p>
                {reviewReasons.length > 0 ? (
                    <ul
                        aria-label="Reasons for review"
                        className="mt-2 list-disc space-y-1 pl-5"
                    >
                        {reviewReasons.map((reason) => (
                            <li key={reason}>{formatStatus(reason)}</li>
                        ))}
                    </ul>
                ) : null}
                {document.status === "UNSUPPORTED" ? (
                    <p className="mt-1">
                        Reprocessing is unavailable for unsupported documents.
                        This workflow currently extracts invoice fields only.
                    </p>
                ) : null}
                {document.status === "REVIEW_REQUIRED" ? (
                    <a
                        className="mt-2 inline-flex min-h-10 items-center font-semibold underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        href="#review-resolution-heading"
                    >
                        Go to review form
                    </a>
                ) : null}
            </FeedbackMessage>
            <ReviewResolutionPanel
                documentId={document.id}
                run={document.current_run}
            />
            <DocumentReprocessingPanel
                documentId={document.id}
                documentStatus={document.status}
                run={document.current_run}
            />
            <DetailSection title="Processing history" open={showProgress}>
                <ProcessingTimeline run={document.current_run} />
            </DetailSection>
            <details className="mt-4 rounded border border-app-border">
                <summary className="min-h-11 cursor-pointer px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">
                    Technical details
                </summary>
                <dl className="grid gap-x-6 gap-y-4 border-t border-app-border p-3 text-sm sm:grid-cols-2">
                    <Value label="Pages" value={String(document.page_count)} />
                    <Value
                        label="Attempts"
                        value={String(document.current_run.attempt_count)}
                    />
                    <Value
                        label="Processing run ID"
                        value={document.current_run.id}
                        technical
                    />
                    {document.current_run.previous_run_id !== null ? (
                        <Value
                            label="Previous processing run ID"
                            value={document.current_run.previous_run_id}
                            technical
                        />
                    ) : null}
                    {document.current_run.failure !== null ? (
                        <>
                            <Value
                                label="Failure stage"
                                value={formatStatus(
                                    document.current_run.failure.stage,
                                )}
                            />
                            <Value
                                label="Failure code"
                                value={document.current_run.failure.code}
                                technical
                            />
                        </>
                    ) : null}
                </dl>
            </details>
            <DetailSection title="Processing results and AI details">
                <ProcessingOutputPanel
                    corrections={
                        document.current_run.review_resolution?.corrections ??
                        []
                    }
                    output={document.current_run.processing_output}
                />
                <AiInvoiceComparison
                    extraction={
                        document.current_run.processing_output
                            ?.invoice_extraction ?? null
                    }
                    proposal={document.current_run.ai_proposal}
                    failure={document.current_run.ai_proposal_failure}
                    execution={document.current_run.ai_execution}
                    applicable={
                        document.current_run.processing_output?.classification
                            ?.document_type === "INVOICE"
                    }
                />
            </DetailSection>
        </section>
    );
}

function DetailSection({
    children,
    open = false,
    title,
}: {
    children: ReactNode;
    open?: boolean;
    title: string;
}) {
    return (
        <details className="mt-4 rounded border border-app-border" open={open}>
            <summary className="min-h-11 cursor-pointer px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">
                {title}
            </summary>
            <div className="border-t border-app-border px-3 pb-4">
                {children}
            </div>
        </details>
    );
}

function Value({
    label,
    technical = false,
    value,
}: {
    label: string;
    technical?: boolean;
    value: string;
}) {
    return (
        <div className="min-w-0">
            <dt className="text-xs font-medium text-app-muted">{label}</dt>
            <dd
                className={`mt-1 ${technical ? "break-all font-mono text-xs" : "break-words"}`}
            >
                {value}
            </dd>
        </div>
    );
}

function formatStatus(status: string): string {
    return status
        .toLowerCase()
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function statusTone(status: VisibleStatus): StatusTone {
    switch (status) {
        case "APPROVED":
        case "COMPLETED":
            return "success";
        case "PROCESSING":
        case "RUNNING":
            return "info";
        case "REVIEW_REQUIRED":
        case "WAITING_RETRY":
            return "warning";
        case "CANCELLED":
        case "FAILED":
        case "REJECTED":
            return "danger";
        case "UNSUPPORTED":
            return "warning";
        default:
            return "neutral";
    }
}

function documentGuidance(document: DocumentStatus): {
    description: string;
    title: string;
    tone: Parameters<typeof FeedbackMessage>[0]["tone"];
} {
    switch (document.status) {
        case "UPLOADED":
            return {
                title: "Waiting to start",
                description:
                    "The document was accepted and is waiting for processing.",
                tone: "info",
            };
        case "PROCESSING":
            return {
                title: "Processing in progress",
                description:
                    "This view refreshes automatically while the document is processed.",
                tone: "info",
            };
        case "REVIEW_REQUIRED":
            return {
                title: "Action required: review this document",
                description:
                    "Check the extracted values against the source, then approve or reject the document.",
                tone: "warning",
            };
        case "APPROVED":
            return {
                title: "Document approved",
                description:
                    "The operator decision is saved. Processing results and the review record are below.",
                tone: "success",
            };
        case "REJECTED":
            return {
                title: "Document rejected",
                description:
                    "The operator decision is saved. The review record is available below.",
                tone: "danger",
            };
        case "UNSUPPORTED":
            return {
                title: "Unsupported document",
                description: unsupportedDocumentMessage(document),
                tone: "warning",
            };
        case "FAILED":
            return {
                title: "Processing stopped after a technical failure",
                description:
                    "Open Technical details to see the failed stage and error code.",
                tone: "danger",
            };
    }
}

function unsupportedDocumentMessage(document: DocumentStatus): string {
    const classification =
        document.current_run.processing_output?.classification;
    if (classification?.document_type === "UNKNOWN") {
        return "The document type could not be recognized. No structured extraction was performed.";
    }
    if (classification !== null && classification !== undefined) {
        return `This ${formatStatus(classification.document_type)} is recognized, but structured extraction is not available for it yet.`;
    }
    return "Structured extraction is not available for this document type yet.";
}
