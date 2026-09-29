import { type DocumentStatus } from "../../api/documentApi";

const STATUS_POLL_INTERVAL_MS = 2_000;
const AI_START_GRACE_MS = 30_000;
const AI_POLL_WINDOW_MS = 6 * 60_000;
type ProcessingRun = DocumentStatus["current_run"];
const terminalRunStatuses = new Set<DocumentStatus["current_run"]["status"]>([
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "REVIEW_REQUIRED",
]);

export function statusPollInterval(
    run: ProcessingRun | undefined,
    now = Date.now(),
): number | false {
    if (run === undefined || !terminalRunStatuses.has(run.status)) {
        return STATUS_POLL_INTERVAL_MS;
    }
    if (run.ai_execution?.status === "RUNNING") {
        return aiExecutionPollExpired(run.ai_execution, now)
            ? false
            : STATUS_POLL_INTERVAL_MS;
    }
    if (
        run.ai_execution == null &&
        run.ai_proposal === null &&
        run.ai_proposal_failure === null &&
        (run.status === "COMPLETED" || run.status === "REVIEW_REQUIRED") &&
        run.processing_output?.classification?.document_type === "INVOICE" &&
        isRecent(run.status_changed_at, AI_START_GRACE_MS, now)
    ) {
        return STATUS_POLL_INTERVAL_MS;
    }
    return false;
}

export function aiExecutionPollExpired(
    execution: NonNullable<ProcessingRun["ai_execution"]>,
    now = Date.now(),
): boolean {
    return !isRecent(execution.started_at, AI_POLL_WINDOW_MS, now);
}

function isRecent(timestamp: string | null, windowMs: number, now: number) {
    if (timestamp === null) return false;
    const age = now - Date.parse(timestamp);
    return Number.isFinite(age) && age >= 0 && age < windowMs;
}
