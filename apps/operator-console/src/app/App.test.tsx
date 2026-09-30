import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";

import { App } from "./App";
import { AppProviders } from "./AppProviders";

beforeEach(() => {
    window.history.replaceState({}, "", "/");
});

test("renders the document intake shell", () => {
    render(
        <AppProviders>
            <App />
        </AppProviders>,
    );

    expect(
        screen.getByRole("heading", { name: "Upload a document" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Choose a PDF")).toHaveAttribute(
        "accept",
        "application/pdf,.pdf",
    );
    expect(
        screen.getByRole("link", { name: "Skip to main content" }),
    ).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("link", { name: "System Map" })).toHaveAttribute(
        "href",
        "/system-map",
    );
});

test("renders the system map at its direct URL", () => {
    window.history.replaceState({}, "", "/system-map");

    render(
        <AppProviders>
            <App />
        </AppProviders>,
    );

    expect(
        screen.getByRole("heading", { level: 1, name: "System Map" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "System Map" })).toHaveAttribute(
        "aria-current",
        "page",
    );
    expect(
        screen.queryByRole("heading", { name: "Upload a document" }),
    ).not.toBeInTheDocument();
});
