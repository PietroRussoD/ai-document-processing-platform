import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
    createDocumentApi,
    type DocumentApi,
    DocumentApiProblem,
    type DocumentStatus,
} from "../../api/documentApi";
import { useOperatorToken } from "../operator-access/operatorToken";
import { ReviewResolutionForm } from "./ReviewResolutionForm";
import { ResolvedReview } from "./ResolvedReview";
import { SourcePdfPreview } from "./SourcePdfPreview";
import { useReviewDraft } from "./reviewDraft";

type ReviewApi = Pick<DocumentApi, "resolveReview"> &
    Partial<Pick<DocumentApi, "getSourceDocument">>;
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
    const { operatorToken, setOperatorToken, isShared } = useOperatorToken();
    const extraction = run.processing_output?.invoice_extraction ?? null;
    const draftKey = `${documentId}:${run.id}:${extraction?.extracted_at ?? "no-extraction"}`;
    const { draft, updateDraft, clearDraft } = useReviewDraft(
        draftKey,
        extraction,
    );
    const reviewNote = draft.reviewNote;
    const resolutionMutation = useMutation({
        mutationFn: ({
            corrections,
            decision,
        }: {
            corrections: Parameters<
                ReviewApi["resolveReview"]
            >[1]["corrections"];
            decision: "APPROVE" | "REJECT";
        }) =>
            api.resolveReview(
                documentId,
                {
                    decision,
                    review_note: reviewNote.trim() || null,
                    corrections,
                },
                operatorToken,
            ),
        onSuccess: async () => {
            if (!isShared) setOperatorToken("");
            clearDraft();
            await queryClient.invalidateQueries({
                queryKey: ["document-status", documentId],
            });
            await queryClient.invalidateQueries({
                queryKey: ["document-work-queue"],
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
    const sourcePreview = api.getSourceDocument ? (
        <SourcePdfPreview
            key={isShared && !operatorToken ? "without-token" : "with-token"}
            api={{ getSourceDocument: api.getSourceDocument }}
            documentId={documentId}
            operatorToken={operatorToken}
        />
    ) : null;

    return (
        <ReviewResolutionForm
            aiProposal={run.ai_proposal}
            draftKey={draftKey}
            errorMessage={resolutionMutation.isError ? failureMessage : null}
            invoiceExtraction={
                run.processing_output?.invoice_extraction ?? null
            }
            isSaving={resolutionMutation.isPending}
            key={
                run.processing_output?.invoice_extraction?.extracted_at ??
                "no-extraction"
            }
            onDecision={(decision, corrections) =>
                resolutionMutation.mutate({ decision, corrections })
            }
            onOperatorTokenChange={setOperatorToken}
            onReviewNoteChange={(reviewNote) =>
                updateDraft((current) => ({ ...current, reviewNote }))
            }
            operatorToken={operatorToken}
            tokenIsShared={isShared}
            reviewNote={reviewNote}
            sourcePreview={sourcePreview}
        />
    );
}
