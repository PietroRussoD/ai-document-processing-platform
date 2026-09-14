import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { App } from "./App";
import { AppProviders } from "./AppProviders";

test("renders the document intake shell", () => {
    render(
        <AppProviders>
            <App />
        </AppProviders>,
    );

    expect(
        screen.getByRole("heading", { name: "Upload a business document" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Choose a PDF")).toHaveAttribute(
        "accept",
        "application/pdf,.pdf",
    );
    expect(
        screen.getByRole("link", { name: "Skip to main content" }),
    ).toHaveAttribute("href", "#main-content");
});
