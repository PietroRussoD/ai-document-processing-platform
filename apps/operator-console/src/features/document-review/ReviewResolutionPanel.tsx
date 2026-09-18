import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, LoaderCircle, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
    createDocumentApi,
    type DocumentApi,
    DocumentApiProblem,
    type DocumentStatus,
} from "../../api/documentApi";
import { ResolvedReview } from "./ResolvedReview";

type ReviewApi = Pick<DocumentApi, "resolveReview">;
type ProcessingRun = DocumentStatus["current_run"];

type ReviewResolutionPanelProps = {
    api?: ReviewApi;
    documentId: string;
    run: ProcessingRun;
};

const defaultApi = createDocumentApi();
const reviewResolutionErrorId = "review-resolution-error";

export function ReviewResolutionPanel({
    api = defaultApi,
    documentId,
    run,
}: ReviewResolutionPanelProps) {
    const queryClient = useQueryClient();
    const errorMessageRef = useRef<HTMLParagraphElement>(null);
    const [operatorToken, setOperatorToken] = useState("");
    const [reviewNote, setReviewNote] = useState("");
    const resolutionMutation = useMutation({
        mutationFn: (decision: "APPROVE" | "REJECT") =>
            api.resolveReview(
                documentId,
                {
                    decision,
                    review_note: reviewNote.trim() || null,
                },
                operatorToken,
            ),
        onSuccess: async () => {
            setOperatorToken("");
            setReviewNote("");
            await queryClient.invalidateQueries({
                queryKey: ["document-status", documentId],
            });
        },
    });

    useEffect(() => {
        if (resolutionMutation.isError) {
            errorMessageRef.current?.focus();
        }
    }, [resolutionMutation.isError]);

    if (run.review_resolution !== null) {
        return <ResolvedReview resolution={run.review_resolution} />;
    }
    if (run.status !== "REVIEW_REQUIRED") {
        return null;
    }

    const failureMessage =
        resolutionMutation.error instanceof DocumentApiProblem
            ? resolutionMutation.error.problem.detail
            : "The review decision could not be saved. Try again.";

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
                            resolutionMutation.isError
                                ? reviewResolutionErrorId
                                : undefined
                        }
                        autoComplete="off"
                        className="mt-1.5 h-10 w-full rounded border border-app-border-strong bg-app-surface px-3 font-mono text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        disabled={resolutionMutation.isPending}
                        onChange={(event) =>
                            setOperatorToken(event.target.value)
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
                        disabled={resolutionMutation.isPending}
                        maxLength={2000}
                        onChange={(event) => setReviewNote(event.target.value)}
                        value={reviewNote}
                    />
                </label>
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
                <button
                    type="button"
                    disabled={!operatorToken || resolutionMutation.isPending}
                    onClick={() => resolutionMutation.mutate("APPROVE")}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded bg-app-accent px-4 text-sm font-semibold text-white hover:bg-app-accent-hover disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                >
                    {resolutionMutation.isPending ? (
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
                    disabled={!operatorToken || resolutionMutation.isPending}
                    onClick={() => resolutionMutation.mutate("REJECT")}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded border border-app-danger px-4 text-sm font-semibold text-app-danger hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                >
                    <XCircle aria-hidden="true" size={17} />
                    Reject document
                </button>
            </div>

            <div aria-live="polite">
                {resolutionMutation.isPending ? (
                    <p role="status" className="mt-4 text-sm text-app-muted">
                        Saving review decision
                    </p>
                ) : null}
                {resolutionMutation.isError ? (
                    <p
                        ref={errorMessageRef}
                        id={reviewResolutionErrorId}
                        role="alert"
                        tabIndex={-1}
                        className="mt-4 text-sm text-app-danger"
                    >
                        {failureMessage}
                    </p>
                ) : null}
            </div>
        </section>
    );
}
