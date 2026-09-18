import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { axe } from "../../test/accessibility";
import { ReviewResolutionForm } from "./ReviewResolutionForm";

test("sends the selected decision when an operator token is present", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();

    render(
        <ReviewResolutionForm
            errorMessage={null}
            isSaving={false}
            onDecision={onDecision}
            onOperatorTokenChange={() => undefined}
            onReviewNoteChange={() => undefined}
            operatorToken="operator-token"
            reviewNote=""
        />,
    );

    await user.click(screen.getByRole("button", { name: "Approve document" }));

    expect(onDecision).toHaveBeenCalledWith("APPROVE");
});

test("moves focus to a review error", async () => {
    render(
        <ReviewResolutionForm
            errorMessage="review authentication was rejected"
            isSaving={false}
            onDecision={() => undefined}
            onOperatorTokenChange={() => undefined}
            onReviewNoteChange={() => undefined}
            operatorToken="operator-token"
            reviewNote=""
        />,
    );

    await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveFocus();
    });
});

test("keeps review controls reachable in a logical keyboard order", async () => {
    const user = userEvent.setup();

    render(
        <ReviewResolutionForm
            errorMessage={null}
            isSaving={false}
            onDecision={() => undefined}
            onOperatorTokenChange={() => undefined}
            onReviewNoteChange={() => undefined}
            operatorToken="operator-token"
            reviewNote=""
        />,
    );

    await user.tab();
    expect(screen.getByLabelText("Operator token")).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText(/Review note/)).toHaveFocus();
    await user.tab();
    expect(
        screen.getByRole("button", { name: "Approve document" }),
    ).toHaveFocus();
    await user.tab();
    expect(
        screen.getByRole("button", { name: "Reject document" }),
    ).toHaveFocus();
});

test("has no detectable accessibility violations", async () => {
    const { container } = render(
        <ReviewResolutionForm
            errorMessage={null}
            isSaving={false}
            onDecision={() => undefined}
            onOperatorTokenChange={() => undefined}
            onReviewNoteChange={() => undefined}
            operatorToken="operator-token"
            reviewNote=""
        />,
    );

    expect((await axe(container)).violations).toEqual([]);
});
