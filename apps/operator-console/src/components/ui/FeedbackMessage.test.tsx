import { render, screen, waitFor } from "@testing-library/react";
import { expect, test } from "vitest";

import { axe } from "../../test/accessibility";
import { FeedbackMessage } from "./FeedbackMessage";

test("renders a semantic alert and focuses it when requested", async () => {
    render(
        <FeedbackMessage focusOnMount role="alert" tone="danger">
            The document could not be uploaded.
        </FeedbackMessage>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("The document could not be uploaded.");
    await waitFor(() => {
        expect(alert).toHaveFocus();
    });
});

test("has no detectable accessibility violations", async () => {
    const { container } = render(
        <FeedbackMessage tone="warning">
            Processing requires an operator review.
        </FeedbackMessage>,
    );

    expect((await axe(container)).violations).toEqual([]);
});
