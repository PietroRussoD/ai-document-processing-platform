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
            invoiceExtraction={invoiceExtraction()}
            isSaving={false}
            onDecision={onDecision}
            onOperatorTokenChange={() => undefined}
            onReviewNoteChange={() => undefined}
            operatorToken="operator-token"
            reviewNote=""
        />,
    );

    await user.click(screen.getByRole("button", { name: "Approve document" }));

    expect(onDecision).toHaveBeenCalledWith("APPROVE", []);
});

test("submits only changed invoice fields with an approval", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();

    render(
        <ReviewResolutionForm
            errorMessage={null}
            invoiceExtraction={invoiceExtraction()}
            isSaving={false}
            onDecision={onDecision}
            onOperatorTokenChange={() => undefined}
            onReviewNoteChange={() => undefined}
            operatorToken="operator-token"
            reviewNote=""
        />,
    );

    await user.clear(screen.getByLabelText("Supplier"));
    await user.type(screen.getByLabelText("Supplier"), "Acme Europe Ltd");
    await user.clear(screen.getByLabelText("Total amount"));
    await user.type(screen.getByLabelText("Total amount"), "159.99");
    await user.click(screen.getByRole("button", { name: "Approve document" }));

    expect(onDecision).toHaveBeenCalledWith("APPROVE", [
        { field: "SUPPLIER_NAME", corrected_value: "Acme Europe Ltd" },
        { field: "TOTAL_AMOUNT", corrected_value: "159.99" },
    ]);
});

test("moves focus to a review error", async () => {
    render(
        <ReviewResolutionForm
            errorMessage="review authentication was rejected"
            invoiceExtraction={null}
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
            invoiceExtraction={null}
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
        screen.getByRole("button", { name: "Reject document" }),
    ).toHaveFocus();
});

test("has no detectable accessibility violations", async () => {
    const { container } = render(
        <ReviewResolutionForm
            errorMessage={null}
            invoiceExtraction={null}
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

function invoiceExtraction() {
    return {
        method: "DETERMINISTIC_RULES" as const,
        invoice_number: "INV-2026-001",
        issue_date: "2026-09-17",
        supplier_name: "Acme Supplies Ltd",
        currency: "EUR",
        total_amount: "149.9900",
        extracted_at: "2026-09-17T18:00:00Z",
    };
}
