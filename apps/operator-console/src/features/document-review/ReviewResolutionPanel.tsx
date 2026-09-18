import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
    createDocumentApi,
    type DocumentApi,
    DocumentApiProblem,
    type DocumentStatus,
} from "../../api/documentApi";
import { ReviewResolutionForm } from "./ReviewResolutionForm";
import { ResolvedReview } from "./ResolvedReview";

type ReviewApi = Pick<DocumentApi, "resolveReview">;
type ProcessingRun = DocumentStatus["current_run"];

type ReviewResolutionPanelProps = {
    api?: ReviewApi;
    documentId: string;
    run: ProcessingRun;
};

const defaultApi = createDocumentApi();

export function ReviewResolutionPanel({
    api = defaultApi,
    documentId,
    run,
}: ReviewResolutionPanelProps) {
    const queryClient = useQueryClient();
    const [operatorToken, setOperatorToken] = useState("");
    const [reviewNote, setReviewNote] = useState("");
    const resolutionMutation = useMutation({
        mutationFn: (decision: "APPROVE" | "REJECT") =>
            api.resolveReview(
                documentId,
                {
                    decision,
                    review_note: reviewNote.trim() || null,
                    corrections: [],
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
        <ReviewResolutionForm
            errorMessage={resolutionMutation.isError ? failureMessage : null}
            isSaving={resolutionMutation.isPending}
            onDecision={(decision) => resolutionMutation.mutate(decision)}
            onOperatorTokenChange={setOperatorToken}
            onReviewNoteChange={setReviewNote}
            operatorToken={operatorToken}
            reviewNote={reviewNote}
        />
    );
}
