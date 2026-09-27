import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";

import { AiInvoiceComparison } from "./AiInvoiceComparison";

const extraction = {
    method: "DETERMINISTIC_RULES" as const,
    invoice_number: "INV-42",
    issue_date: "2026-09-16",
    supplier_name: "Acme Ltd",
    currency: "EUR",
    total_amount: "12.50",
    extracted_at: "2026-09-16T12:00:04Z",
};

const proposal = {
    schema_version: 1,
    provider: "OLLAMA" as const,
    model_reference: "qwen3:8b",
    model_digest: null,
    prompt_version: "invoice-v1",
    selected_text_sha256: "a".repeat(64),
    status: "PARTIAL" as const,
    invoice_number: "INV-42",
    issue_date: null,
    supplier_name: "Acme Europe Ltd",
    currency: "EUR",
    total_amount: "12.50",
    issues: [{ code: "MISSING_FIELD" as const, field: "ISSUE_DATE" as const }],
    proposed_at: "2026-09-16T12:00:06Z",
};

test("does not imply an AI result when none is recorded", () => {
    const { container } = render(
        <AiInvoiceComparison
            extraction={extraction}
            proposal={null}
            failure={null}
        />,
    );

    expect(container).toBeEmptyDOMElement();
});

test("compares rule-based fields with a partial advisory proposal", () => {
    render(
        <AiInvoiceComparison
            extraction={extraction}
            proposal={proposal}
            failure={null}
        />,
    );

    expect(
        screen.getByRole("heading", { name: "AI proposal comparison" }),
    ).toBeVisible();
    expect(screen.getByText("Advisory")).toBeVisible();
    expect(screen.getByText("Partial")).toBeVisible();
    expect(screen.getByText(/Ollama.*qwen3:8b.*invoice-v1/)).toBeVisible();
    const supplierRow = screen.getByText("Supplier").parentElement;
    expect(supplierRow).not.toBeNull();
    expect(within(supplierRow!).getByText("Acme Ltd")).toBeVisible();
    expect(within(supplierRow!).getByText("Acme Europe Ltd")).toBeVisible();
    const dateRow = screen.getByText("Issue date").parentElement;
    expect(dateRow).not.toBeNull();
    expect(within(dateRow!).getByText("Not found")).toBeVisible();
    expect(screen.getByText("Missing Field: Issue Date")).toBeVisible();
    expect(
        screen.queryByText(proposal.selected_text_sha256),
    ).not.toBeInTheDocument();
});

test("shows a bounded provider failure instead of a proposal", () => {
    render(
        <AiInvoiceComparison
            extraction={extraction}
            proposal={null}
            failure={{
                provider: "OLLAMA",
                model_reference: "qwen3:8b",
                code: "TIMEOUT",
                failed_at: "2026-09-16T12:00:06Z",
            }}
        />,
    );

    expect(screen.getByText("AI proposal unavailable: Timeout.")).toBeVisible();
    expect(screen.queryByText("Invoice number")).not.toBeInTheDocument();
});
