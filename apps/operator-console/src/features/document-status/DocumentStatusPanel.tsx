import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import {
    createDocumentApi,
    type DocumentApi,
    type DocumentStatus,
} from "../../api/documentApi";
import { Button } from "../../components/ui/Button";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { ProcessingOutputPanel } from "../processing-output/ProcessingOutputPanel";
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
            statusPollInterval(query.state.data?.current_run.status),
    });

    if (statusQuery.isPending) {
        return (
            <section className="mt-4 border border-app-border bg-app-surface p-5">
                <h3 className="text-sm font-semibold">Persisted status</h3>
                <FeedbackMessage className="mt-3" tone="info">
                    Loading persisted status
                </FeedbackMessage>
            </section>
        );
    }

    if (statusQuery.isError) {
        return (
            <section className="mt-4 border border-app-border bg-app-surface p-5">
                <h3 className="text-sm font-semibold">Persisted status</h3>
                <FeedbackMessage className="mt-3" role="alert" tone="danger">
                    The persisted status could not be loaded.
                </FeedbackMessage>
                <Button
                    className="mt-4"
                    onClick={() => void statusQuery.refetch()}
                    size="sm"
                >
                    <RefreshCw aria-hidden="true" size={16} />
                    Retry status
                </Button>
            </section>
        );
    }

    const document = statusQuery.data;
    return (
        <section className="mt-4 border border-app-border bg-app-surface p-5">
            <h3 className="text-sm font-semibold">Persisted status</h3>
            {document.current_run.status === "COMPLETED" ? (
                <FeedbackMessage className="mt-4" tone="success">
                    Processing results are ready.
                </FeedbackMessage>
            ) : null}
            {document.current_run.status === "REVIEW_REQUIRED" ? (
                <FeedbackMessage className="mt-4" tone="warning">
                    Processing requires an operator review.
                </FeedbackMessage>
            ) : null}
            {document.current_run.failure !== null ? (
                <FeedbackMessage className="mt-4" tone="danger">
                    Processing stopped after a terminal technical failure.
                </FeedbackMessage>
            ) : null}
            <dl className="mt-4 grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
                <StatusValue label="Document status" status={document.status} />
                <StatusValue
                    label="Processing status"
                    status={document.current_run.status}
                />
                <Value label="Filename" value={document.original_filename} />
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
                            value={formatStatus(document.current_run.failure.stage)}
                        />
                        <Value
                            label="Failure code"
                            value={document.current_run.failure.code}
                            technical
                        />
                    </>
                ) : null}
            </dl>
            <ProcessingOutputPanel
                corrections={
                    document.current_run.review_resolution?.corrections ?? []
                }
                output={document.current_run.processing_output}
            />
            <ReviewResolutionPanel
                documentId={document.id}
                run={document.current_run}
            />
            <DocumentReprocessingPanel
                documentId={document.id}
                run={document.current_run}
            />
            <ProcessingTimeline run={document.current_run} />
        </section>
    );
}

function StatusValue({
    label,
    status,
}: {
    label: string;
    status: VisibleStatus;
}) {
    return (
        <div>
            <dt className="mb-1.5 text-xs font-medium text-app-muted">
                {label}
            </dt>
            <dd>
                <StatusBadge
                    label={formatStatus(status)}
                    tone={statusTone(status)}
                />
            </dd>
        </div>
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
        default:
            return "neutral";
    }
}
