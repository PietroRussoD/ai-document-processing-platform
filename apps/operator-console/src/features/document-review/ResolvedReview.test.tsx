import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { axe } from "../../test/accessibility";
import { ResolvedReview } from "./ResolvedReview";

test("renders an approved review outcome", () => {
    render(
        <ResolvedReview
            resolution={{
                decision: "APPROVE",
                reviewer_id: "operator-42",
                review_note: "Supplier evidence verified.",
                resolved_at: "2026-09-17T18:00:00Z",
                corrections: [
                    {
                        field: "SUPPLIER_NAME",
                        corrected_value: "Acme Europe Ltd",
                        source: "MANUAL",
                        corrected_at: "2026-09-17T18:00:00Z",
                    },
                    {
                        field: "TOTAL_AMOUNT",
                        corrected_value: "159.9900",
                        source: "AI_PROPOSAL",
                        corrected_at: "2026-09-17T18:00:00Z",
                    },
                ],
            }}
        />,
    );

    expect(screen.getByText("Review resolved")).toBeVisible();
    expect(screen.getByText("Approved")).toBeVisible();
    expect(screen.getByText("operator-42")).toBeVisible();
    expect(screen.getByText("Supplier evidence verified.")).toBeVisible();
    expect(screen.getByText("Recorded corrections")).toBeVisible();
    expect(screen.getByText("Acme Europe Ltd")).toBeVisible();
    expect(screen.getByText("159.9900")).toBeVisible();
    expect(screen.getByText("AI proposal selected")).toBeVisible();
});

test("renders a rejected outcome without a review note", () => {
    render(
        <ResolvedReview
            resolution={{
                decision: "REJECT",
                reviewer_id: "operator-42",
                review_note: null,
                resolved_at: "2026-09-17T18:00:00Z",
                corrections: [],
            }}
        />,
    );

    expect(screen.getByText("Rejected")).toBeVisible();
    expect(screen.getByText("No note provided")).toBeVisible();
    const outcome = screen.getByRole("region", { name: "Review resolved" });
    expect(outcome).toHaveClass("border-red-200", "bg-red-50");
    expect(outcome).not.toHaveClass("bg-app-success-surface");
});

test.each(["APPROVE", "REJECT"] as const)(
    "has no detectable accessibility violations for %s outcomes",
    async (decision) => {
        const { container } = render(
            <ResolvedReview
                resolution={{
                    decision,
                    reviewer_id: "operator-42",
                    review_note: "Supplier evidence verified.",
                    resolved_at: "2026-09-17T18:00:00Z",
                    corrections: [],
                }}
            />,
        );

        expect((await axe(container)).violations).toEqual([]);
    },
);
