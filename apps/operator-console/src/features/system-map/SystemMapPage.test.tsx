import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { axe } from "../../test/accessibility";
import { SystemMapPage } from "./SystemMapPage";

test("shows the implemented processing path and component evidence", () => {
    render(<SystemMapPage />);

    const path = within(
        screen.getByRole("region", { name: "Processing path" }),
    );
    expect(path.getByRole("list")).toHaveTextContent("Operator console");
    expect(path.getByRole("list")).toHaveTextContent("Temporal");
    expect(
        screen.getByRole("heading", { name: "Operator console" }),
    ).toBeVisible();

    fireEvent.click(path.getByRole("button", { name: /Dispatcher/ }));

    expect(screen.getByRole("heading", { name: "Dispatcher" })).toBeVisible();
    expect(screen.getByText(/Committed pending start requests/)).toBeVisible();
    expect(screen.getByRole("link", { name: "View source" })).toHaveAttribute(
        "href",
        expect.stringContaining("src/document_platform/dispatcher.py"),
    );
});

test("marks observability as optional and has no basic accessibility violations", async () => {
    const { container } = render(<SystemMapPage />);

    const supporting = within(
        screen.getByRole("region", { name: "Supporting components" }),
    );
    const observability = supporting.getByRole("button", {
        name: /Observability/,
    });
    fireEvent.click(observability);

    expect(within(observability).getByText("Optional")).toBeVisible();
    expect(
        screen.getByRole("heading", { name: "Observability" }),
    ).toBeVisible();
    expect((await axe(container)).violations).toEqual([]);
});

test("links the project evidence without requiring a running backend", () => {
    render(<SystemMapPage />);

    const references = within(
        screen.getByRole("region", { name: "Technical references" }),
    );
    expect(references.getAllByRole("link")).toHaveLength(6);
    expect(
        references.getByRole("link", { name: "OpenAPI contract" }),
    ).toHaveAttribute(
        "href",
        expect.stringContaining(
            "docs/contracts/document-platform.openapi.json",
        ),
    );
    expect(
        references.getByRole("link", { name: "Architecture decisions" }),
    ).toHaveAttribute(
        "href",
        expect.stringContaining("/tree/main/docs/decisions"),
    );
    expect(
        references.getByRole("link", { name: "Security and limitations" }),
    ).toHaveAttribute(
        "href",
        expect.stringContaining("docs/security-and-limitations.md"),
    );
});

test("keeps component selection focus and offers a keyboard shortcut to its details", async () => {
    const user = userEvent.setup();
    render(<SystemMapPage />);
    const dispatcher = within(
        screen.getByRole("region", { name: "Processing path" }),
    ).getByRole("button", { name: /Dispatcher/ });
    await user.click(dispatcher);
    expect(dispatcher).toHaveFocus();
    expect(dispatcher).toHaveAttribute("aria-pressed", "true");
    expect(
        screen
            .getAllByRole("status")
            .some((status) =>
                status.textContent?.includes(
                    "Component selected. Dispatcher. Details updated.",
                ),
            ),
    ).toBe(true);
    await user.tab();
    const shortcut = screen.getByRole("link", {
        name: "Go to component details",
    });
    expect(shortcut).toHaveFocus();
    expect(shortcut).toHaveAttribute("href", "#system-node-details-heading");
    expect(screen.getByRole("heading", { name: "Dispatcher" })).toHaveAttribute(
        "tabindex",
        "-1",
    );
    expect(
        screen.getByRole("region", { name: "Dispatcher" }),
    ).not.toHaveAttribute("aria-live");
});
