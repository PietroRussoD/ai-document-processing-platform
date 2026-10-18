import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";

import { App } from "./App";
import { AppProviders } from "./AppProviders";

beforeEach(() => {
    window.history.replaceState({}, "", "/");
});

test("renders the document shell and gates intake behind operator access", () => {
    render(
        <AppProviders>
            <App />
        </AppProviders>,
    );

    expect(
        screen.getByRole("heading", { level: 1, name: "Documents" }),
    ).toBeVisible();
    expect(
        screen.getByRole("region", { name: "Operator access" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Operator token")).toBeVisible();
    expect(
        screen.queryByRole("heading", { name: "Upload a document" }),
    ).not.toBeInTheDocument();
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
