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
                corrections: [],
            }}
        />,
    );

    expect(screen.getByText("Review resolved")).toBeVisible();
    expect(screen.getByText("Approved")).toBeVisible();
    expect(screen.getByText("operator-42")).toBeVisible();
    expect(screen.getByText("Supplier evidence verified.")).toBeVisible();
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
});

test("has no detectable accessibility violations", async () => {
    const { container } = render(
        <ResolvedReview
            resolution={{
                decision: "APPROVE",
                reviewer_id: "operator-42",
                review_note: "Supplier evidence verified.",
                resolved_at: "2026-09-17T18:00:00Z",
                corrections: [],
            }}
        />,
    );

    expect((await axe(container)).violations).toEqual([]);
});
