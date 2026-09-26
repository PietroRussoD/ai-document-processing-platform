import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { axe } from "../../test/accessibility";
import { SystemMapPage } from "./SystemMapPage";

test("shows the implemented processing path and component evidence", () => {
    render(<SystemMapPage />);

    expect(screen.getByRole("list")).toHaveTextContent("Operator console");
    expect(screen.getByRole("list")).toHaveTextContent("Temporal");
    expect(
        screen.getByRole("heading", { name: "Operator console" }),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: /Dispatcher/ }));

    expect(screen.getByRole("heading", { name: "Dispatcher" })).toBeVisible();
    expect(screen.getByText(/Committed pending start requests/)).toBeVisible();
    expect(screen.getByRole("link", { name: "View source" })).toHaveAttribute(
        "href",
        expect.stringContaining("src/document_platform/dispatcher.py"),
    );
});

test("marks observability as optional and has no basic accessibility violations", async () => {
    const { container } = render(<SystemMapPage />);

    fireEvent.click(screen.getByRole("button", { name: /Observability/ }));

    expect(screen.getByText("Optional")).toBeVisible();
    expect(
        screen.getByRole("heading", { name: "Observability" }),
    ).toBeVisible();
    expect((await axe(container)).violations).toEqual([]);
});
