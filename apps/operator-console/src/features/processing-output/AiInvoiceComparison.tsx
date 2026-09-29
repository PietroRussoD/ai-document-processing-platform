import { Sparkles } from "lucide-react";

import { type DocumentStatus } from "../../api/documentApi";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { aiExecutionPollExpired } from "../document-status/statusPolling";

type ProcessingRun = DocumentStatus["current_run"];
type InvoiceExtraction = NonNullable<
    NonNullable<ProcessingRun["processing_output"]>["invoice_extraction"]
>;
type AiProposal = NonNullable<ProcessingRun["ai_proposal"]>;

type AiInvoiceComparisonProps = {
    extraction: InvoiceExtraction | null;
    proposal: ProcessingRun["ai_proposal"];
    failure: ProcessingRun["ai_proposal_failure"];
    execution?: ProcessingRun["ai_execution"];
    applicable?: boolean;
};

const fields = [
    ["Invoice number", "invoice_number"],
    ["Issue date", "issue_date"],
    ["Supplier", "supplier_name"],
    ["Currency", "currency"],
    ["Total amount", "total_amount"],
] as const;

export function AiInvoiceComparison({
    extraction,
    proposal,
    failure,
    execution,
    applicable = false,
}: AiInvoiceComparisonProps) {
    if (
        proposal === null &&
        failure === null &&
        execution == null &&
        !applicable
    ) {
        return null;
    }

    return (
        <section
            className="mt-6 border-t border-app-border pt-5"
            aria-labelledby="ai-comparison-heading"
        >
            <div className="flex flex-wrap items-center gap-2">
                <Sparkles
                    aria-hidden="true"
                    size={16}
                    className="text-app-accent"
                />
                <h3
                    id="ai-comparison-heading"
                    className="text-sm font-semibold"
                >
                    AI proposal comparison
                </h3>
                <StatusBadge label="Advisory" tone="info" />
                {execution != null ? (
                    <StatusBadge
                        label={`Execution ${formatLabel(execution.status).toLowerCase()}`}
                        tone={
                            execution.status === "FAILED"
                                ? "warning"
                                : "neutral"
                        }
                    />
                ) : null}
                {proposal !== null ? (
                    <StatusBadge
                        label={formatLabel(proposal.status)}
                        tone={
                            proposal.status === "VALID" ? "success" : "warning"
                        }
                    />
                ) : null}
            </div>

            {execution?.status === "DISABLED" ? (
                <FeedbackMessage className="mt-4" tone="info">
                    AI proposals are disabled for this run.
                </FeedbackMessage>
            ) : null}
            {execution?.status === "RUNNING" ? (
                <FeedbackMessage className="mt-4" tone="info">
                    {aiExecutionPollExpired(execution)
                        ? "AI execution still reports running; automatic updates are paused."
                        : "AI proposal pending."}
                </FeedbackMessage>
            ) : null}
            {execution == null && proposal === null && failure === null ? (
                <FeedbackMessage className="mt-4" tone="info">
                    AI execution state is not recorded.
                </FeedbackMessage>
            ) : null}
            {execution?.status === "COMPLETED" && proposal === null ? (
                <FeedbackMessage className="mt-4" tone="warning">
                    AI execution completed; proposal details are unavailable.
                </FeedbackMessage>
            ) : null}
            {execution?.status === "FAILED" && failure === null ? (
                <FeedbackMessage className="mt-4" tone="warning">
                    AI proposal failed; failure details are unavailable.
                </FeedbackMessage>
            ) : null}

            {failure !== null ? (
                <FeedbackMessage className="mt-4" tone="warning">
                    AI proposal unavailable: {formatLabel(failure.code)}.
                </FeedbackMessage>
            ) : null}

            {proposal !== null ? (
                <>
                    <p className="mt-2 break-all text-xs text-app-muted">
                        {formatLabel(proposal.provider)} ·{" "}
                        {proposal.model_reference} · prompt{" "}
                        {proposal.prompt_version}
                    </p>
                    <div className="mt-4 hidden grid-cols-[minmax(7rem,0.7fr)_minmax(0,1fr)_minmax(0,1fr)] gap-x-4 border-b border-app-border pb-2 text-xs text-app-muted sm:grid">
                        <span>Field</span>
                        <span>Rule-based</span>
                        <span>AI proposal</span>
                    </div>
                    <dl
                        aria-label="Rule-based and advisory AI invoice values"
                        className="text-sm"
                    >
                        {fields.map(([label, field]) => (
                            <div
                                key={field}
                                className="grid grid-cols-2 gap-x-4 gap-y-1 border-b border-app-border py-2.5 sm:grid-cols-[minmax(7rem,0.7fr)_minmax(0,1fr)_minmax(0,1fr)]"
                            >
                                <dt className="col-span-2 font-medium sm:col-span-1">
                                    {label}
                                </dt>
                                <dd className="min-w-0 break-words">
                                    <span className="block text-xs text-app-muted sm:sr-only">
                                        Rule-based
                                    </span>
                                    {displayValue(extraction?.[field])}
                                </dd>
                                <dd className="min-w-0 break-words">
                                    <span className="block text-xs text-app-muted sm:sr-only">
                                        AI proposal
                                    </span>
                                    {displayValue(proposal[field])}
                                </dd>
                            </div>
                        ))}
                    </dl>
                    {proposal.issues.length > 0 ? (
                        <div className="mt-4 text-sm">
                            <h4 className="font-medium">Proposal issues</h4>
                            <ul className="mt-1 list-disc space-y-1 pl-5 text-app-muted">
                                {proposal.issues.map((issue, index) => (
                                    <li
                                        key={`${issue.code}-${issue.field ?? "response"}-${index}`}
                                    >
                                        {formatLabel(issue.code)}
                                        {issue.field === null
                                            ? ""
                                            : `: ${formatLabel(issue.field)}`}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ) : null}
                </>
            ) : null}
        </section>
    );
}

function displayValue(value: string | null | undefined): string {
    return value ?? "Not found";
}

function formatLabel(value: AiProposal["status"] | string): string {
    return value
        .toLowerCase()
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}
