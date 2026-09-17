import { type DocumentStatus } from "../../api/documentApi";

const STATUS_POLL_INTERVAL_MS = 2_000;
const terminalRunStatuses = new Set<DocumentStatus["current_run"]["status"]>([
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "REVIEW_REQUIRED",
]);

export function statusPollInterval(
    status: DocumentStatus["current_run"]["status"] | undefined,
): number | false {
    return status !== undefined && terminalRunStatuses.has(status)
        ? false
        : STATUS_POLL_INTERVAL_MS;
}
