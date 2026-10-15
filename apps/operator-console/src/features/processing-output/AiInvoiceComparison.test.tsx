import { render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

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

test("explains that parsed AI fields still need comparison with the PDF", () => {
    render(
        <AiInvoiceComparison
            extraction={extraction}
            proposal={{
                ...proposal,
                status: "VALID",
                issue_date: "2026-09-16",
                issues: [],
            }}
            failure={null}
        />,
    );

    expect(screen.getByText("Fields parsed")).toBeVisible();
    expect(
        screen.getByText(
            "All five fields were returned in a format the application can read. Compare their values with the PDF; this does not confirm they are correct or approve the invoice.",
        ),
    ).toBeVisible();
    expect(screen.queryByText("Valid")).not.toBeInTheDocument();
});

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

test("does not label an unknown invoice execution as disabled", () => {
    render(
        <AiInvoiceComparison
            extraction={extraction}
            proposal={null}
            failure={null}
            applicable
        />,
    );
    expect(
        screen.getByText("AI execution state is not recorded."),
    ).toBeVisible();
    expect(screen.queryByText(/disabled/)).not.toBeInTheDocument();
});

test.each([
    ["DISABLED", "AI proposals are disabled for this run."],
    ["COMPLETED", "AI execution completed; proposal details are unavailable."],
    ["FAILED", "AI proposal failed; failure details are unavailable."],
] as const)("shows persisted %s execution feedback", (status, message) => {
    render(
        <AiInvoiceComparison
            extraction={extraction}
            proposal={null}
            failure={null}
            execution={{
                status,
                started_at: null,
                finished_at: "2026-09-29T10:00:00Z",
                status_changed_at: "2026-09-29T10:00:00Z",
            }}
        />,
    );
    expect(screen.getByText(message)).toBeVisible();
});

test.each([
    [0, "AI proposal pending."],
    [
        360_000,
        "AI execution still reports running; automatic updates are paused.",
    ],
])("shows running feedback after %s ms", (age, message) => {
    const at = Date.parse("2026-09-29T10:00:00Z");
    const clock = vi.spyOn(Date, "now").mockReturnValue(at + Number(age));
    try {
        render(
            <AiInvoiceComparison
                extraction={extraction}
                proposal={null}
                failure={null}
                execution={{
                    status: "RUNNING",
                    started_at: "2026-09-29T10:00:00Z",
                    finished_at: null,
                    status_changed_at: "2026-09-29T10:00:00Z",
                }}
            />,
        );
        expect(screen.getByText(message)).toBeVisible();
        expect(screen.getByRole("status")).toBeVisible();
    } finally {
        clock.mockRestore();
    }
});
