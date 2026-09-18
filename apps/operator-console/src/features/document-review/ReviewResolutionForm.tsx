import { CheckCircle2, CircleAlert, LoaderCircle, XCircle } from "lucide-react";

import { FeedbackMessage } from "../../components/ui/FeedbackMessage";

export type ReviewDecision = "APPROVE" | "REJECT";

type ReviewResolutionFormProps = {
    errorMessage: string | null;
    isSaving: boolean;
    onDecision: (decision: ReviewDecision) => void;
    onOperatorTokenChange: (operatorToken: string) => void;
    onReviewNoteChange: (reviewNote: string) => void;
    operatorToken: string;
    reviewNote: string;
};

const reviewResolutionErrorId = "review-resolution-error";

export function ReviewResolutionForm({
    errorMessage,
    isSaving,
    onDecision,
    onOperatorTokenChange,
    onReviewNoteChange,
    operatorToken,
    reviewNote,
}: ReviewResolutionFormProps) {
    return (
        <section
            className="mt-6 border border-amber-300 bg-amber-50 p-5"
            aria-labelledby="review-resolution-heading"
        >
            <div className="flex items-start gap-3">
                <CircleAlert
                    aria-hidden="true"
                    className="mt-0.5 shrink-0 text-amber-800"
                    size={20}
                />
                <div>
                    <h3
                        id="review-resolution-heading"
                        className="text-sm font-semibold text-amber-950"
                    >
                        Resolve operator review
                    </h3>
                    <p className="mt-1 text-sm text-amber-900">
                        Approve or reject the document after checking the
                        persisted processing results.
                    </p>
                </div>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium text-app-foreground">
                    Operator token
                    <input
                        required
                        aria-describedby={
                            errorMessage !== null
                                ? reviewResolutionErrorId
                                : undefined
                        }
                        autoComplete="off"
                        className="mt-1.5 h-10 w-full rounded border border-app-border-strong bg-app-surface px-3 font-mono text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        disabled={isSaving}
                        onChange={(event) =>
                            onOperatorTokenChange(event.target.value)
                        }
                        spellCheck={false}
                        type="password"
                        value={operatorToken}
                    />
                </label>
                <label className="block text-sm font-medium text-app-foreground">
                    Review note{" "}
                    <span className="font-normal text-app-muted">
                        (optional)
                    </span>
                    <textarea
                        className="mt-1.5 min-h-20 w-full resize-y rounded border border-app-border-strong bg-app-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        disabled={isSaving}
                        maxLength={2000}
                        onChange={(event) =>
                            onReviewNoteChange(event.target.value)
                        }
                        value={reviewNote}
                    />
                </label>
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
                <button
                    type="button"
                    disabled={!operatorToken || isSaving}
                    onClick={() => onDecision("APPROVE")}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded bg-app-accent px-4 text-sm font-semibold text-white hover:bg-app-accent-hover disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                >
                    {isSaving ? (
                        <LoaderCircle
                            aria-hidden="true"
                            className="motion-safe:animate-spin"
                            size={17}
                        />
                    ) : (
                        <CheckCircle2 aria-hidden="true" size={17} />
                    )}
                    Approve document
                </button>
                <button
                    type="button"
                    disabled={!operatorToken || isSaving}
                    onClick={() => onDecision("REJECT")}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded border border-app-danger px-4 text-sm font-semibold text-app-danger hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                >
                    <XCircle aria-hidden="true" size={17} />
                    Reject document
                </button>
            </div>

            <div>
                {isSaving ? (
                    <FeedbackMessage className="mt-4" tone="info">
                        Saving review decision
                    </FeedbackMessage>
                ) : null}
                {errorMessage !== null ? (
                    <FeedbackMessage
                        id={reviewResolutionErrorId}
                        className="mt-4"
                        focusOnMount
                        role="alert"
                        tone="danger"
                    >
                        {errorMessage}
                    </FeedbackMessage>
                ) : null}
            </div>
        </section>
    );
}
