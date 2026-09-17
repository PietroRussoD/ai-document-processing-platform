import { CheckCircle2, XCircle } from "lucide-react";

import type { DocumentStatus } from "../../api/documentApi";
import { StatusBadge } from "../../components/ui/StatusBadge";

type ReviewResolution = NonNullable<
    DocumentStatus["current_run"]["review_resolution"]
>;

type ResolvedReviewProps = {
    resolution: ReviewResolution;
};

export function ResolvedReview({ resolution }: ResolvedReviewProps) {
    const approved = resolution.decision === "APPROVE";

    return (
        <section
            className="mt-6 border border-app-success-border bg-app-success-surface p-5"
            aria-labelledby="review-outcome-heading"
        >
            <div className="flex items-center gap-2">
                {approved ? (
                    <CheckCircle2
                        aria-hidden="true"
                        className="text-app-success"
                        size={20}
                    />
                ) : (
                    <XCircle
                        aria-hidden="true"
                        className="text-app-danger"
                        size={20}
                    />
                )}
                <h3
                    id="review-outcome-heading"
                    className="text-sm font-semibold"
                >
                    Review resolved
                </h3>
                <StatusBadge
                    label={approved ? "Approved" : "Rejected"}
                    tone={approved ? "success" : "danger"}
                />
            </div>
            <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                <ReviewValue label="Reviewer" value={resolution.reviewer_id} />
                <ReviewValue
                    label="Resolved at"
                    value={resolution.resolved_at}
                    technical
                />
                <ReviewValue
                    label="Review note"
                    value={resolution.review_note ?? "No note provided"}
                />
            </dl>
        </section>
    );
}

function ReviewValue({
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
                className={`mt-1 break-words ${technical ? "font-mono text-xs" : ""}`}
            >
                {value}
            </dd>
        </div>
    );
}
