import { useQuery } from "@tanstack/react-query";
import {
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    RefreshCw,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
    createDocumentApi,
    type DocumentApi,
    type DocumentStatus,
    type DocumentWorkQueue,
    type DocumentWorkQueuePage,
} from "../../api/documentApi";
import { Button } from "../../components/ui/Button";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { DocumentStatusPanel } from "../document-status/DocumentStatusPanel";

type WorkQueueApi = Pick<DocumentApi, "getStatus" | "listWorkQueue">;
type QueueItem = DocumentWorkQueuePage["items"][number];

type DocumentWorkQueuesPanelProps = {
    api?: WorkQueueApi;
};

const defaultApi = createDocumentApi();
const queues: readonly {
    id: DocumentWorkQueue;
    label: string;
}[] = [
    { id: "ACTIVE", label: "Active" },
    { id: "REVIEW", label: "Needs review" },
    { id: "FAILED", label: "Failed" },
    { id: "UNSUPPORTED", label: "Unsupported" },
];

export function DocumentWorkQueuesPanel({
    api = defaultApi,
}: DocumentWorkQueuesPanelProps) {
    const [queue, setQueue] = useState<DocumentWorkQueue>("ACTIVE");
    const [offset, setOffset] = useState(0);
    const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
        () => new URL(window.location.href).searchParams.get("documentId"),
    );
    const workQueueQuery = useQuery({
        queryKey: ["document-work-queue", queue, offset],
        queryFn: ({ signal }) => api.listWorkQueue(queue, offset, signal),
        refetchInterval: 15_000,
    });

    useEffect(() => {
        function syncSelectedDocument() {
            setSelectedDocumentId(
                new URL(window.location.href).searchParams.get("documentId"),
            );
        }

        window.addEventListener("popstate", syncSelectedDocument);
        return () =>
            window.removeEventListener("popstate", syncSelectedDocument);
    }, []);

    function selectQueue(nextQueue: DocumentWorkQueue) {
        setQueue(nextQueue);
        setOffset(0);
        setSelectedDocumentId(null);
        updateDocumentUrl(null);
    }

    function toggleDocumentDetails(documentId: string) {
        const nextDocumentId =
            selectedDocumentId === documentId ? null : documentId;
        setSelectedDocumentId(nextDocumentId);
        updateDocumentUrl(nextDocumentId);
    }

    return (
        <section
            aria-labelledby="work-queues-heading"
            className="mt-12 border-t border-app-border pt-8"
        >
            <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-app-accent">
                        Operations
                    </p>
                    <h2
                        id="work-queues-heading"
                        className="text-2xl font-semibold"
                    >
                        Document work queues
                    </h2>
                </div>
                <Button
                    aria-label="Refresh work queue"
                    disabled={workQueueQuery.isFetching}
                    onClick={() => void workQueueQuery.refetch()}
                    size="sm"
                >
                    <RefreshCw
                        aria-hidden="true"
                        className={
                            workQueueQuery.isFetching
                                ? "motion-safe:animate-spin"
                                : undefined
                        }
                        size={16}
                    />
                    Refresh
                </Button>
            </div>

            <div
                aria-label="Filter document work queue"
                className="mt-5 flex flex-wrap gap-2"
                role="group"
            >
                {queues.map((item) => (
                    <Button
                        key={item.id}
                        aria-pressed={queue === item.id}
                        onClick={() => selectQueue(item.id)}
                        size="sm"
                        variant={queue === item.id ? "primary" : "secondary"}
                    >
                        {item.label}
                    </Button>
                ))}
            </div>

            <p className="mt-3 text-sm text-app-muted" aria-live="polite">
                {workQueueQuery.data === undefined
                    ? "Showing the latest 25 documents"
                    : `${workQueueQuery.data.total} total · showing ${workQueueQuery.data.total === 0 ? 0 : offset + 1}-${offset + workQueueQuery.data.items.length}`}
            </p>

            {workQueueQuery.isPending ? (
                <FeedbackMessage className="mt-4" tone="info">
                    Loading {queueLabel(queue).toLowerCase()} documents
                </FeedbackMessage>
            ) : null}

            {workQueueQuery.isError ? (
                <div className="mt-4">
                    <FeedbackMessage role="alert" tone="danger">
                        The work queue could not be loaded.
                    </FeedbackMessage>
                    <Button
                        className="mt-3"
                        onClick={() => void workQueueQuery.refetch()}
                        size="sm"
                    >
                        <RefreshCw aria-hidden="true" size={16} />
                        Retry
                    </Button>
                </div>
            ) : null}

            {workQueueQuery.isSuccess &&
            workQueueQuery.data.items.length === 0 ? (
                <div className="mt-4">
                    <FeedbackMessage tone="info">
                        {offset === 0
                            ? `No ${queueLabel(queue).toLowerCase()} documents found.`
                            : "No documents remain on this page. Return to the previous page."}
                    </FeedbackMessage>
                    {offset > 0 ? (
                        <Button
                            className="mt-3"
                            onClick={() =>
                                setOffset((current) =>
                                    Math.max(0, current - 25),
                                )
                            }
                            size="sm"
                        >
                            <ChevronLeft aria-hidden="true" size={16} />
                            Previous page
                        </Button>
                    ) : null}
                </div>
            ) : null}

            {workQueueQuery.isSuccess &&
            workQueueQuery.data.items.length > 0 ? (
                <>
                    <ul className="mt-4 divide-y divide-app-border border-y border-app-border">
                        {workQueueQuery.data.items.map((item) => (
                            <QueueRow
                                key={item.document_id}
                                item={item}
                                isSelected={
                                    selectedDocumentId === item.document_id
                                }
                                onSelect={() =>
                                    toggleDocumentDetails(item.document_id)
                                }
                            />
                        ))}
                    </ul>
                    {workQueueQuery.data.total > workQueueQuery.data.limit ? (
                        <nav
                            aria-label="Work queue pages"
                            className="mt-4 flex items-center justify-between gap-3"
                        >
                            <Button
                                disabled={
                                    offset === 0 || workQueueQuery.isFetching
                                }
                                onClick={() =>
                                    setOffset((current) =>
                                        Math.max(
                                            0,
                                            current - workQueueQuery.data.limit,
                                        ),
                                    )
                                }
                                size="sm"
                            >
                                <ChevronLeft aria-hidden="true" size={16} />
                                Previous
                            </Button>
                            <p
                                className="text-sm text-app-muted"
                                aria-live="polite"
                            >
                                Page{" "}
                                {Math.floor(
                                    offset / workQueueQuery.data.limit,
                                ) + 1}{" "}
                                of{" "}
                                {Math.ceil(
                                    workQueueQuery.data.total /
                                        workQueueQuery.data.limit,
                                )}
                            </p>
                            <Button
                                disabled={
                                    offset + workQueueQuery.data.limit >=
                                        workQueueQuery.data.total ||
                                    workQueueQuery.isFetching
                                }
                                onClick={() =>
                                    setOffset(
                                        (current) =>
                                            current + workQueueQuery.data.limit,
                                    )
                                }
                                size="sm"
                            >
                                Next
                                <ChevronRight aria-hidden="true" size={16} />
                            </Button>
                        </nav>
                    ) : null}
                </>
            ) : null}

            <div id="selected-document-details" className="mt-4">
                {selectedDocumentId !== null ? (
                    <DocumentStatusPanel
                        api={api}
                        documentId={selectedDocumentId}
                    />
                ) : null}
            </div>
        </section>
    );
}

function updateDocumentUrl(documentId: string | null) {
    const url = new URL(window.location.href);
    if (url.searchParams.get("documentId") === documentId) {
        return;
    }
    if (documentId === null) {
        url.searchParams.delete("documentId");
    } else {
        url.searchParams.set("documentId", documentId);
    }
    const nextUrl = `${url.pathname}${url.search}${url.hash}`;
    if (documentId === null) {
        window.history.replaceState({}, "", nextUrl);
    } else {
        window.history.pushState({}, "", nextUrl);
    }
}

function QueueRow({
    item,
    isSelected,
    onSelect,
}: {
    item: QueueItem;
    isSelected: boolean;
    onSelect: () => void;
}) {
    return (
        <li className="py-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                    <p className="break-words font-medium">
                        {item.original_filename}
                    </p>
                    <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-app-muted">
                        <div>
                            <dt className="sr-only">Document status</dt>
                            <dd>
                                <StatusBadge
                                    label={formatDocumentStatus(item.status)}
                                    tone={statusTone(item.status)}
                                />
                            </dd>
                        </div>
                        <div>
                            <dt className="inline">Received </dt>
                            <dd className="inline">
                                <time dateTime={item.accepted_at}>
                                    {formatDate(item.accepted_at)}
                                </time>
                            </dd>
                        </div>
                        <div>
                            <dt className="inline">Attempts </dt>
                            <dd className="inline">{item.attempt_count}</dd>
                        </div>
                        {item.failure !== null ? (
                            <div className="basis-full">
                                <dt className="inline">Failure </dt>
                                <dd className="inline">
                                    {formatStage(item.failure.stage)} ·{" "}
                                    <code>{item.failure.code}</code>
                                </dd>
                            </div>
                        ) : null}
                    </dl>
                </div>
                <Button
                    aria-controls="selected-document-details"
                    aria-expanded={isSelected}
                    onClick={onSelect}
                    size="sm"
                >
                    <ChevronDown
                        aria-hidden="true"
                        className={isSelected ? "rotate-180" : undefined}
                        size={16}
                    />
                    {isSelected ? "Hide details" : "View details"}
                </Button>
            </div>
            <p className="mt-2 truncate font-mono text-xs text-app-muted">
                {item.document_id}
            </p>
        </li>
    );
}

function queueLabel(queue: DocumentWorkQueue): string {
    return queues.find((item) => item.id === queue)?.label ?? "Documents";
}

function formatDocumentStatus(status: DocumentStatus["status"]): string {
    return status.replaceAll("_", " ");
}

function statusTone(
    status: DocumentStatus["status"],
): Parameters<typeof StatusBadge>[0]["tone"] {
    if (status === "FAILED" || status === "REJECTED") {
        return "danger";
    }
    if (status === "REVIEW_REQUIRED" || status === "UNSUPPORTED") {
        return "warning";
    }
    if (status === "APPROVED") {
        return "success";
    }
    return "info";
}

function formatStage(
    stage: NonNullable<QueueItem["failure"]>["stage"],
): string {
    return stage.replaceAll("_", " ").toLowerCase();
}

function formatDate(value: string): string {
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(new Date(value));
}
