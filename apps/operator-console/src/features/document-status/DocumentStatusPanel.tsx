import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, RefreshCw } from "lucide-react";

import {
    createDocumentApi,
    type DocumentApi,
    type DocumentStatus,
} from "../../api/documentApi";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { ProcessingOutputPanel } from "../processing-output/ProcessingOutputPanel";
import { ProcessingTimeline } from "../processing-output/ProcessingTimeline";
import { ReviewResolutionPanel } from "../document-review/ReviewResolutionPanel";
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
                <p role="status" className="mt-3 text-sm text-app-muted">
                    Loading persisted status
                </p>
            </section>
        );
    }

    if (statusQuery.isError) {
        return (
            <section className="mt-4 border border-app-border bg-app-surface p-5">
                <h3 className="text-sm font-semibold">Persisted status</h3>
                <p role="alert" className="mt-3 text-sm text-app-danger">
                    The persisted status could not be loaded.
                </p>
                <button
                    type="button"
                    onClick={() => void statusQuery.refetch()}
                    className="mt-4 inline-flex h-9 items-center gap-2 rounded border border-app-border-strong px-3 text-sm font-semibold hover:bg-app-canvas focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                >
                    <RefreshCw aria-hidden="true" size={16} />
                    Retry status
                </button>
            </section>
        );
    }

    const document = statusQuery.data;
    return (
        <section className="mt-4 border border-app-border bg-app-surface p-5">
            <h3 className="text-sm font-semibold">Persisted status</h3>
            {document.current_run.status === "COMPLETED" ? (
                <div
                    role="status"
                    className="mt-4 flex items-center gap-2 border-l-2 border-app-success pl-3 text-sm text-app-success"
                >
                    <CheckCircle2 aria-hidden="true" size={18} />
                    <p>Processing results are ready.</p>
                </div>
            ) : null}
            {document.current_run.status === "REVIEW_REQUIRED" ? (
                <div
                    role="status"
                    className="mt-4 flex items-center gap-2 border-l-2 border-app-warning pl-3 text-sm text-app-warning"
                >
                    <CircleAlert aria-hidden="true" size={18} />
                    <p>Processing requires an operator review.</p>
                </div>
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
            </dl>
            <ProcessingOutputPanel
                output={document.current_run.processing_output}
            />
            <ReviewResolutionPanel
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

function formatStatus(status: VisibleStatus): string {
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
