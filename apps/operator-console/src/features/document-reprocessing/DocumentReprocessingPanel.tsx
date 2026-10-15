import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, RotateCcw } from "lucide-react";
import { useState } from "react";

import {
    createDocumentApi,
    type DocumentApi,
    DocumentApiProblem,
    type DocumentReprocessing,
    type DocumentStatus,
} from "../../api/documentApi";
import { Button } from "../../components/ui/Button";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";

type ReprocessingApi = Pick<DocumentApi, "requestReprocessing">;
type ProcessingRun = DocumentStatus["current_run"];

type DocumentReprocessingPanelProps = {
    api?: ReprocessingApi;
    documentId: string;
    documentStatus: DocumentStatus["status"];
    idempotencyKeyGenerator?: () => string;
    run: ProcessingRun;
};

const terminalRunStatuses = new Set<ProcessingRun["status"]>([
    "CANCELLED",
    "COMPLETED",
    "FAILED",
]);
const reprocessableDocumentStatuses = new Set<DocumentStatus["status"]>([
    "APPROVED",
    "REJECTED",
    "FAILED",
    "UPLOADED",
    "PROCESSING",
]);
const defaultApi = createDocumentApi();

export function DocumentReprocessingPanel({
    api = defaultApi,
    documentId,
    documentStatus,
    idempotencyKeyGenerator = () => crypto.randomUUID(),
    run,
}: DocumentReprocessingPanelProps) {
    const queryClient = useQueryClient();
    const [operatorToken, setOperatorToken] = useState("");
    const [reason, setReason] = useState("");
    const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
    const [lastRequest, setLastRequest] = useState<DocumentReprocessing | null>(
        null,
    );
    const reprocessingMutation = useMutation({
        mutationFn: ({
            idempotencyKey: requestIdempotencyKey,
            reason: requestReason,
        }: {
            idempotencyKey: string;
            reason: string;
        }) =>
            api.requestReprocessing(
                documentId,
                { reason: requestReason },
                operatorToken,
                requestIdempotencyKey,
            ),
        onSuccess: async (reprocessing) => {
            setOperatorToken("");
            setReason("");
            setIdempotencyKey(null);
            setLastRequest(reprocessing);
            await queryClient.invalidateQueries({
                queryKey: ["document-status", documentId],
            });
        },
    });

    if (lastRequest !== null) {
        return <ReprocessingRequestOutcome reprocessing={lastRequest} />;
    }

    if (
        !terminalRunStatuses.has(run.status) ||
        !reprocessableDocumentStatuses.has(documentStatus)
    ) {
        return null;
    }

    const failureMessage =
        reprocessingMutation.error instanceof DocumentApiProblem
            ? reprocessingMutation.error.problem.detail
            : "The reprocessing request could not be submitted. Try again.";
    const errorId = "document-reprocessing-error";
    const trimmedReason = reason.trim();

    function submitReprocessing() {
        const requestIdempotencyKey =
            idempotencyKey ?? idempotencyKeyGenerator();
        setIdempotencyKey(requestIdempotencyKey);
        reprocessingMutation.mutate({
            idempotencyKey: requestIdempotencyKey,
            reason: trimmedReason,
        });
    }

    return (
        <section
            className="mt-6 border border-blue-200 bg-blue-50 p-5"
            aria-labelledby="document-reprocessing-heading"
        >
            <div className="flex items-start gap-3">
                <RotateCcw
                    aria-hidden="true"
                    className="mt-0.5 shrink-0 text-blue-800"
                    size={20}
                />
                <div>
                    <h3
                        id="document-reprocessing-heading"
                        className="text-sm font-semibold text-blue-950"
                    >
                        Request controlled reprocessing
                    </h3>
                    <p className="mt-1 text-sm text-blue-900">
                        Creates a new processing run while preserving the
                        completed run and its outputs.
                    </p>
                </div>
            </div>

            <form
                className="mt-5 grid gap-4 sm:grid-cols-2"
                onSubmit={(event) => {
                    event.preventDefault();
                    submitReprocessing();
                }}
            >
                <label className="block text-sm font-medium text-app-foreground">
                    Operator token
                    <input
                        required
                        aria-describedby={
                            reprocessingMutation.isError ? errorId : undefined
                        }
                        autoComplete="off"
                        className="mt-1.5 h-10 w-full rounded border border-app-border-strong bg-app-surface px-3 font-mono text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        disabled={reprocessingMutation.isPending}
                        onChange={(event) =>
                            setOperatorToken(event.target.value)
                        }
                        spellCheck={false}
                        type="password"
                        value={operatorToken}
                    />
                </label>
                <label className="block text-sm font-medium text-app-foreground">
                    Reprocessing reason
                    <textarea
                        required
                        aria-describedby={
                            reprocessingMutation.isError ? errorId : undefined
                        }
                        className="mt-1.5 min-h-20 w-full resize-y rounded border border-app-border-strong bg-app-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        disabled={reprocessingMutation.isPending}
                        maxLength={500}
                        onChange={(event) => {
                            setReason(event.target.value);
                            setIdempotencyKey(null);
                        }}
                        value={reason}
                    />
                </label>
                <div className="sm:col-span-2">
                    <Button
                        disabled={
                            !operatorToken ||
                            !trimmedReason ||
                            reprocessingMutation.isPending
                        }
                        type="submit"
                        variant="secondary"
                    >
                        {reprocessingMutation.isPending ? (
                            <LoaderCircle
                                aria-hidden="true"
                                className="motion-safe:animate-spin"
                                size={17}
                            />
                        ) : (
                            <RotateCcw aria-hidden="true" size={17} />
                        )}
                        Request reprocessing
                    </Button>
                </div>
            </form>

            {reprocessingMutation.isPending ? (
                <FeedbackMessage className="mt-4" tone="info">
                    Creating a new processing run
                </FeedbackMessage>
            ) : null}
            {reprocessingMutation.isError ? (
                <FeedbackMessage
                    id={errorId}
                    className="mt-4"
                    focusOnMount
                    role="alert"
                    tone="danger"
                >
                    {failureMessage}
                </FeedbackMessage>
            ) : null}
        </section>
    );
}

function ReprocessingRequestOutcome({
    reprocessing,
}: {
    reprocessing: DocumentReprocessing;
}) {
    return (
        <section
            className="mt-6 border border-app-success-border bg-app-success-surface p-5"
            aria-labelledby="reprocessing-request-outcome-heading"
        >
            <div className="flex items-center gap-2 text-app-success">
                <CheckCircle2 aria-hidden="true" size={20} />
                <h3
                    id="reprocessing-request-outcome-heading"
                    className="font-semibold"
                >
                    {reprocessing.replayed
                        ? "Existing reprocessing request restored"
                        : "Reprocessing requested"}
                </h3>
            </div>
            <p className="mt-2 text-sm text-app-success">
                The replacement run has been queued. The persisted status will
                refresh as processing continues.
            </p>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <Identifier
                    label="Reprocessing operation ID"
                    value={reprocessing.operation_id}
                />
                <Identifier
                    label="Source processing run ID"
                    value={reprocessing.source_run_id}
                />
                <Identifier
                    label="Replacement processing run ID"
                    value={reprocessing.replacement_run_id}
                />
            </dl>
        </section>
    );
}

function Identifier({ label, value }: { label: string; value: string }) {
    return (
        <div className="min-w-0">
            <dt className="text-xs font-medium text-app-muted">{label}</dt>
            <dd className="mt-1 break-all font-mono text-xs">{value}</dd>
        </div>
    );
}
