import { CheckCircle2, Circle, LoaderCircle } from "lucide-react";

import { type DocumentStatus } from "../../api/documentApi";

type ProcessingOutput = NonNullable<
    DocumentStatus["current_run"]["processing_output"]
>;
type ProcessingRun = DocumentStatus["current_run"];
type TimelineState = "completed" | "in-progress" | "pending";

type ProcessingTimelineProps = {
    run: ProcessingRun;
};

type TimelineStage = {
    label: string;
    state: TimelineState;
    detail: string;
};

export function ProcessingTimeline({ run }: ProcessingTimelineProps) {
    const stages = buildTimelineStages(run);

    return (
        <section
            className="mt-6 border-t border-app-border pt-5"
            aria-labelledby="processing-progress-heading"
        >
            <h3
                id="processing-progress-heading"
                className="text-sm font-semibold"
            >
                Processing progress
            </h3>
            <ol className="mt-4 space-y-3" aria-label="Processing stages">
                {stages.map((stage) => (
                    <li
                        key={stage.label}
                        className="flex items-start gap-3 text-sm"
                    >
                        <StageIcon state={stage.state} />
                        <div>
                            <p className="font-medium">{stage.label}</p>
                            <p className="mt-0.5 text-app-muted">
                                {stage.detail}
                            </p>
                        </div>
                    </li>
                ))}
            </ol>
        </section>
    );
}

function StageIcon({ state }: { state: TimelineState }) {
    const className = "mt-0.5 shrink-0";
    if (state === "completed") {
        return (
            <CheckCircle2
                aria-label="Completed"
                className={`${className} text-app-success`}
                size={18}
            />
        );
    }
    if (state === "in-progress") {
        return (
            <LoaderCircle
                aria-label="In progress"
                className={`${className} animate-spin text-app-accent`}
                size={18}
            />
        );
    }
    return (
        <Circle
            aria-label="Pending"
            className={`${className} text-app-muted`}
            size={18}
        />
    );
}

function buildTimelineStages(run: ProcessingRun): TimelineStage[] {
    const output = run.processing_output;
    const automationFinished = [
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "REVIEW_REQUIRED",
    ].includes(run.status);

    return [
        stage(
            "Text extraction",
            output?.embedded_text !== null &&
                output?.embedded_text !== undefined,
            automationFinished,
            "Extracting readable PDF text.",
        ),
        ocrStage(output, automationFinished),
        stage(
            "Canonical text selection",
            output?.selected_text !== null &&
                output?.selected_text !== undefined,
            automationFinished,
            "Selecting the source used by downstream stages.",
        ),
        stage(
            "Document classification",
            output?.classification !== null &&
                output?.classification !== undefined,
            automationFinished,
            "Classifying the selected document text.",
        ),
        invoiceExtractionStage(output, automationFinished),
        invoiceValidationStage(output, automationFinished),
        completionStage(run),
    ];
}

function invoiceExtractionStage(
    output: ProcessingOutput | null,
    automationFinished: boolean,
): TimelineStage {
    if (
        output?.classification === null ||
        output?.classification === undefined
    ) {
        return stage(
            "Invoice extraction",
            false,
            automationFinished,
            "Waiting for document classification.",
        );
    }
    if (output.classification.document_type !== "INVOICE") {
        return {
            label: "Invoice extraction",
            state: "completed",
            detail: "Not applicable to this document type.",
        };
    }
    return stage(
        "Invoice extraction",
        output.invoice_extraction !== null,
        automationFinished,
        "Extracting structured invoice fields.",
    );
}

function invoiceValidationStage(
    output: ProcessingOutput | null,
    automationFinished: boolean,
): TimelineStage {
    if (
        output?.classification === null ||
        output?.classification === undefined
    ) {
        return stage(
            "Invoice validation",
            false,
            automationFinished,
            "Waiting for document classification.",
        );
    }
    if (output.classification.document_type !== "INVOICE") {
        return {
            label: "Invoice validation",
            state: "completed",
            detail: "Not applicable to this document type.",
        };
    }
    if (
        output?.invoice_validation !== null &&
        output?.invoice_validation !== undefined
    ) {
        return {
            label: "Invoice validation",
            state: "completed",
            detail:
                output.invoice_validation.decision === "AUTO_APPROVE"
                    ? "Invoice approved automatically."
                    : "Invoice requires an operator review.",
        };
    }
    return stage(
        "Invoice validation",
        false,
        automationFinished,
        "Checking extracted invoice fields.",
    );
}

function completionStage(run: ProcessingRun): TimelineStage {
    if (run.status === "COMPLETED") {
        return {
            label: "Processing completion",
            state: "completed",
            detail: "All implemented stages finished.",
        };
    }
    if (run.status === "REVIEW_REQUIRED") {
        return {
            label: "Review handoff",
            state: "completed",
            detail: "Automated processing paused for operator review.",
        };
    }
    return {
        label: "Processing completion",
        state: "pending",
        detail: "Waiting for all processing stages to finish.",
    };
}

function ocrStage(
    output: ProcessingOutput | null,
    terminal: boolean,
): TimelineStage {
    if (output?.ocr_text !== null && output?.ocr_text !== undefined) {
        return {
            label: "OCR fallback",
            state: "completed",
            detail: "OCR fallback completed.",
        };
    }
    if (output?.embedded_text?.quality === "SUFFICIENT") {
        return {
            label: "OCR fallback",
            state: "completed",
            detail: "Skipped because embedded text was sufficient.",
        };
    }
    return stage(
        "OCR fallback",
        false,
        terminal,
        "Running OCR when embedded text needs improvement.",
    );
}

function stage(
    label: string,
    complete: boolean,
    terminal: boolean,
    pendingDetail: string,
): TimelineStage {
    return {
        label,
        state: complete ? "completed" : terminal ? "pending" : "in-progress",
        detail: complete
            ? "Completed."
            : terminal
              ? "Not completed."
              : pendingDetail,
    };
}
