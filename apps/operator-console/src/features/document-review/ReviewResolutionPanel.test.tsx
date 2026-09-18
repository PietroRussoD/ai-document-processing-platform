import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type PropsWithChildren } from "react";
import { expect, test, vi } from "vitest";

import {
    type DocumentApi,
    DocumentApiProblem,
    type DocumentStatus,
    type ReviewResolution,
} from "../../api/documentApi";
import { axe } from "../../test/accessibility";
import { ReviewResolutionPanel } from "./ReviewResolutionPanel";

const DOCUMENT_ID = "11111111-1111-4111-8111-111111111111";

test("submits an approval with the token and optional note", async () => {
    let completeReview!: (resolution: ReviewResolution) => void;
    const reviewCompletion = new Promise<ReviewResolution>((resolve) => {
        completeReview = resolve;
    });
    const resolveReview = vi
        .fn<DocumentApi["resolveReview"]>()
        .mockReturnValue(reviewCompletion);

    render(
        <ReviewResolutionPanel
            api={{ resolveReview }}
            documentId={DOCUMENT_ID}
            run={reviewRequiredRun()}
        />,
        { wrapper: QueryWrapper },
    );

    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "operator-token" },
    });
    fireEvent.change(screen.getByLabelText(/Review note/), {
        target: { value: "Checked the supplier statement." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve document" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
        "Saving review decision",
    );
    expect(resolveReview).toHaveBeenCalledWith(
        DOCUMENT_ID,
        {
            decision: "APPROVE",
            review_note: "Checked the supplier statement.",
        },
        "operator-token",
    );
    completeReview({
        processing_run_id: "22222222-2222-4222-8222-222222222222",
        decision: "APPROVE",
        reviewer_id: "operator-42",
        resolved_at: "2026-09-17T18:00:00Z",
        replayed: false,
    });
    await waitFor(() => {
        expect(screen.getByLabelText("Operator token")).toHaveValue("");
    });
});

test("shows a safe review failure message", async () => {
    const problem = {
        type: "urn:problem:review-authentication-rejected",
        title: "Review authentication rejected",
        status: 401,
        detail: "review authentication was rejected",
    };
    const resolveReview = vi
        .fn<DocumentApi["resolveReview"]>()
        .mockRejectedValue(new DocumentApiProblem(problem));

    render(
        <ReviewResolutionPanel
            api={{ resolveReview }}
            documentId={DOCUMENT_ID}
            run={reviewRequiredRun()}
        />,
        { wrapper: QueryWrapper },
    );

    fireEvent.change(screen.getByLabelText("Operator token"), {
        target: { value: "incorrect-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject document" }));

    const errorMessage = await screen.findByRole("alert");
    expect(errorMessage).toHaveTextContent(problem.detail);
    expect(errorMessage).toHaveFocus();
    expect(screen.getByLabelText("Operator token")).toHaveAttribute(
        "aria-describedby",
        "review-resolution-error",
    );
});

test("shows the immutable outcome after a refresh", () => {
    render(
        <ReviewResolutionPanel
            documentId={DOCUMENT_ID}
            run={{
                ...reviewRequiredRun(),
                status: "COMPLETED",
                review_resolution: {
                    decision: "REJECT",
                    reviewer_id: "operator-42",
                    review_note: "Missing supplier evidence.",
                    resolved_at: "2026-09-17T18:00:00Z",
                },
            }}
        />,
        { wrapper: QueryWrapper },
    );

    expect(screen.getByText("Review resolved")).toBeVisible();
    expect(screen.getByText("Rejected")).toBeVisible();
    expect(screen.getByText("operator-42")).toBeVisible();
    expect(screen.getByText("Missing supplier evidence.")).toBeVisible();
    expect(screen.queryByLabelText("Operator token")).not.toBeInTheDocument();
});

test("has no detectable accessibility violations while a review is required", async () => {
    const { container } = render(
        <ReviewResolutionPanel
            documentId={DOCUMENT_ID}
            run={reviewRequiredRun()}
        />,
        { wrapper: QueryWrapper },
    );

    expect((await axe(container)).violations).toEqual([]);
});

function reviewRequiredRun(): DocumentStatus["current_run"] {
    return {
        id: "22222222-2222-4222-8222-222222222222",
        status: "REVIEW_REQUIRED",
        queued_at: "2026-09-17T17:00:00Z",
        started_at: "2026-09-17T17:00:01Z",
        status_changed_at: "2026-09-17T17:00:02Z",
        finished_at: null,
        attempt_count: 1,
        processing_output: null,
        review_resolution: null,
    };
}

function QueryWrapper({ children }: PropsWithChildren) {
    const client = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    });
    return (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
}
