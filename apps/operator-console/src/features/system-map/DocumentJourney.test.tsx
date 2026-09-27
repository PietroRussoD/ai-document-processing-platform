import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { axe } from "../../test/accessibility";
import { DocumentJourney } from "./DocumentJourney";

test("shows the auto-approval path and its implementation evidence", () => {
    render(<DocumentJourney />);

    expect(
        screen.getByRole("button", { name: /Auto-approved invoice/ }),
    ).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /Apply validation/ }));

    expect(
        screen.getByRole("heading", { name: "Apply validation" }),
    ).toBeVisible();
    expect(screen.getByText(/AUTO_APPROVE decision/)).toBeVisible();
    expect(
        screen.getByRole("link", { name: "View implementation" }),
    ).toHaveAttribute(
        "href",
        expect.stringContaining("apply_invoice_validation.py"),
    );
});

test("switching paths resets the selected step and keeps failure evidence", async () => {
    const { container } = render(<DocumentJourney />);

    fireEvent.click(screen.getByRole("button", { name: /Apply validation/ }));
    fireEvent.click(
        screen.getByRole("button", { name: "Failure and reprocessing" }),
    );

    expect(screen.getByRole("heading", { name: "Accept PDF" })).toBeVisible();
    fireEvent.click(
        screen.getByRole("button", { name: /Record terminal failure/ }),
    );
    expect(screen.getByText(/Temporal history remains failed/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Request a new run/ }));
    expect(screen.getByText(/does not erase the failed run/)).toBeVisible();
    expect((await axe(container)).violations).toEqual([]);
});

test("review path distinguishes review-required and final states", () => {
    render(<DocumentJourney />);

    fireEvent.click(
        screen.getByRole("button", { name: "Review-required invoice" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /Request review/ }));
    expect(
        screen.getAllByText("Document REVIEW_REQUIRED · run REVIEW_REQUIRED"),
    ).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: /Resolve review/ }));
    expect(
        screen.getByText(/original extraction remains immutable/),
    ).toBeVisible();
});
