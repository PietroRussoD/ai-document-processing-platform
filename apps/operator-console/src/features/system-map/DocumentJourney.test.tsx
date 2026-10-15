import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

test("explains unsupported documents as a terminal business outcome", () => {
    render(<DocumentJourney />);

    fireEvent.click(
        screen.getByRole("button", { name: "Unsupported document" }),
    );
    fireEvent.click(
        screen.getByRole("button", { name: /Complete as unsupported/ }),
    );

    expect(
        screen.getAllByText("Document UNSUPPORTED · run COMPLETED"),
    ).toHaveLength(2);
    expect(screen.getByText(/commit atomically/)).toBeVisible();
});

test("announces step changes without moving focus and resets feedback when the outcome changes", async () => {
    const user = userEvent.setup();
    render(<DocumentJourney />);
    const validation = screen.getByRole("button", { name: /Apply validation/ });
    await user.click(validation);
    expect(validation).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent(
        /Step .* selected. Apply validation/,
    );
    await user.tab();
    expect(
        screen.getByRole("link", { name: "Go to step details" }),
    ).toHaveFocus();
    expect(
        screen.getByRole("link", { name: "Go to step details" }),
    ).toHaveAttribute("href", "#journey-step-details-heading");
    expect(
        screen.getByRole("region", { name: "Apply validation" }),
    ).not.toHaveAttribute("aria-live");
    const outcome = screen.getByRole("button", {
        name: "Failure and reprocessing",
    });
    await user.click(outcome);
    expect(outcome).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent(
        /Failure and reprocessing. Step 1 of .* selected. Accept PDF/,
    );
    expect(screen.getByRole("heading", { name: "Accept PDF" })).toHaveAttribute(
        "tabindex",
        "-1",
    );
});
