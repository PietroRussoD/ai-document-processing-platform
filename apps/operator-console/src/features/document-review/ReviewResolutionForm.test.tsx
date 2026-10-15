import { render, screen, waitFor, within } from "@testing-library/react";
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
        {
            field: "SUPPLIER_NAME",
            corrected_value: "Acme Europe Ltd",
            source: "MANUAL",
        },
        { field: "TOTAL_AMOUNT", corrected_value: "159.99", source: "MANUAL" },
    ]);
});

test("allows selecting a proposal while recording its source", async () => {
    const onDecision = vi.fn();
    const user = userEvent.setup();

    const { container } = render(
        <ReviewResolutionForm
            aiProposal={{
                schema_version: 1,
                provider: "OLLAMA",
                model_reference: "qwen3:8b",
                model_digest: null,
                prompt_version: "invoice-fields-v1",
                selected_text_sha256: "a".repeat(64),
                status: "VALID",
                invoice_number: "INV-2026-001",
                issue_date: "2026-09-18",
                supplier_name: "Acme AI Ltd",
                currency: "EUR",
                total_amount: "159.99",
                issues: [],
                proposed_at: "2026-09-17T18:00:00Z",
            }}
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

    await user.click(
        screen.getByRole("button", { name: "Use suggestion for Supplier" }),
    );
    const supplier = screen.getByLabelText("Supplier");
    const supplierField = within(supplier.parentElement!);
    expect(
        supplierField.getByText("Acme AI Ltd", { exact: true }),
    ).toBeVisible();
    expect(supplierField.getByText("From AI suggestion")).toBeVisible();
    expect(
        screen.queryByRole("button", { name: "Use suggestion for Currency" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve document" }));

    expect(onDecision).toHaveBeenCalledWith("APPROVE", [
        {
            field: "SUPPLIER_NAME",
            corrected_value: "Acme AI Ltd",
            source: "AI_PROPOSAL",
        },
    ]);
    await user.clear(supplier);
    await user.type(supplier, "Verified Supplier");
    expect(supplierField.getByText("Manual correction")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Approve document" }));
    expect(onDecision).toHaveBeenLastCalledWith("APPROVE", [
        {
            field: "SUPPLIER_NAME",
            corrected_value: "Verified Supplier",
            source: "MANUAL",
        },
    ]);
    await user.click(
        screen.getByRole("button", {
            name: "Restore extracted value for Supplier",
        }),
    );
    expect(supplier).toHaveValue("Acme Supplies Ltd");
    expect(supplier).toHaveFocus();
    expect(
        supplierField.getByText("Extracted value", { exact: true }),
    ).toBeVisible();
    expect(
        supplierField.queryByText("Manual correction"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve document" }));
    expect(onDecision).toHaveBeenLastCalledWith("APPROVE", []);
    expect((await axe(container)).violations).toEqual([]);
});

test("clears a correction to a missing value and removes its validation error", async () => {
    const user = userEvent.setup();
    render(
        <ReviewResolutionForm
            errorMessage={null}
            invoiceExtraction={{ ...invoiceExtraction(), total_amount: null }}
            isSaving={false}
            onDecision={vi.fn()}
            onOperatorTokenChange={() => undefined}
            onReviewNoteChange={() => undefined}
            operatorToken="operator-token"
            reviewNote=""
        />,
    );
    const amount = screen.getByLabelText("Total amount");
    await user.type(amount, "-5");
    await user.click(screen.getByRole("button", { name: "Approve document" }));
    expect(amount).toHaveAttribute("aria-invalid", "true");
    await user.click(
        screen.getByRole("button", {
            name: "Clear correction for Total amount",
        }),
    );
    expect(amount).toHaveValue(null);
    expect(amount).not.toHaveAttribute("aria-invalid");
    expect(amount).toHaveFocus();
    expect(
        within(amount.parentElement!).getByText("Not extracted"),
    ).toBeVisible();
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

test("keeps credentials, source, fields and review note in task order", async () => {
    const user = userEvent.setup();
    const onDecision = vi.fn();
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
            sourcePreview={<button type="button">View source PDF</button>}
        />,
    );
    await user.tab();
    expect(screen.getByLabelText("Operator token")).toHaveFocus();
    await user.tab();
    expect(
        screen.getByRole("button", { name: "Invoice fields" }),
    ).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Source PDF" })).toHaveFocus();
    await user.tab();
    expect(
        screen.getByRole("button", { name: "View source PDF" }),
    ).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText("Invoice number")).toHaveFocus();
    for (const label of [
        "Issue date",
        "Supplier",
        "Currency",
        "Total amount",
    ]) {
        await user.tab();
        expect(screen.getByLabelText(label)).toHaveFocus();
    }
    await user.tab();
    expect(screen.getByLabelText(/Review note/)).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Approve document" }));
    expect(onDecision).toHaveBeenCalledWith("APPROVE", []);
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
