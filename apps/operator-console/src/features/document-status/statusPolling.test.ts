import { expect, test } from "vitest";

import type { DocumentStatus } from "../../api/documentApi";
import { aiExecutionPollExpired, statusPollInterval } from "./statusPolling";

type Run = DocumentStatus["current_run"];
const AT = "2026-09-29T10:00:00Z";
const NOW = Date.parse(AT);

function run(status: Run["status"] = "COMPLETED"): Run {
    return {
        id: "22222222-2222-4222-8222-222222222222",
        previous_run_id: null,
        status,
        queued_at: AT,
        started_at: AT,
        status_changed_at: AT,
        finished_at: AT,
        attempt_count: 1,
        failure: null,
        review_resolution: null,
        ai_proposal: null,
        ai_proposal_failure: null,
        ai_execution: null,
        processing_output: {
            embedded_text: null,
            ocr_text: null,
            selected_text: null,
            classification: {
                document_type: "INVOICE",
                reason: "KEYWORD_MATCHED",
                classified_at: AT,
            },
            invoice_extraction: null,
            invoice_validation: null,
        },
    };
}

test.each(["COMPLETED", "REVIEW_REQUIRED"] as const)(
    "polls %s invoices briefly until AI starts",
    (status) => {
        expect(statusPollInterval(run(status), NOW + 29_999)).toBe(2_000);
        expect(statusPollInterval(run(status), NOW + 30_000)).toBe(false);
    },
);

test.each(["COMPLETED", "REVIEW_REQUIRED"] as const)(
    "continues polling a %s run while recorded AI is running",
    (status) => {
        const result = run(status);
        result.ai_execution = {
            status: "RUNNING",
            started_at: AT,
            finished_at: null,
            status_changed_at: AT,
        };
        expect(statusPollInterval(result, NOW + 359_999)).toBe(2_000);
        expect(statusPollInterval(result, NOW + 360_000)).toBe(false);
    },
);

test.each(["DISABLED", "COMPLETED", "FAILED"] as const)(
    "stops polling once AI records %s",
    (status) => {
        const result = run();
        result.ai_execution = {
            status,
            started_at: status === "DISABLED" ? null : AT,
            finished_at: AT,
            status_changed_at: AT,
        };
        expect(statusPollInterval(result, NOW)).toBe(false);
    },
);

test.each(["UNKNOWN", "PURCHASE_ORDER", "CREDIT_NOTE"] as const)(
    "does not wait for an invoice proposal on a %s document",
    (documentType) => {
        const result = run();
        result.processing_output!.classification!.document_type = documentType;
        expect(statusPollInterval(result, NOW)).toBe(false);
    },
);

test("does not wait for AI after deterministic failure or cancellation", () => {
    expect(statusPollInterval(run("FAILED"), NOW)).toBe(false);
    expect(statusPollInterval(run("CANCELLED"), NOW)).toBe(false);
});

test("preserves polling for active deterministic processing", () => {
    const result = run("RUNNING");
    result.ai_execution = {
        status: "DISABLED",
        started_at: null,
        finished_at: AT,
        status_changed_at: AT,
    };
    expect(statusPollInterval(result, NOW)).toBe(2_000);
});

test("legacy provider outcome ends the unknown-state grace period", () => {
    const result = run();
    result.ai_proposal_failure = {
        provider: "OLLAMA",
        model_reference: "synthetic-model",
        code: "TIMEOUT",
        failed_at: AT,
    };
    expect(statusPollInterval(result, NOW)).toBe(false);
});

test.each([null, "invalid-date", "2026-09-29T10:01:00Z"])(
    "does not poll indefinitely with missing or unusable AI start %s",
    (startedAt) => {
        const result = run();
        const execution = {
            status: "RUNNING" as const,
            started_at: startedAt,
            finished_at: null,
            status_changed_at: AT,
        };
        result.ai_execution = execution;
        expect(statusPollInterval(result, NOW)).toBe(false);
        expect(aiExecutionPollExpired(execution, NOW)).toBe(true);
    },
);

test("does not apply a start grace period without invoice classification", () => {
    const result = run();
    result.processing_output = null;
    expect(statusPollInterval(result, NOW)).toBe(false);
});
