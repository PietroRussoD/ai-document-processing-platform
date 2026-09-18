import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { axe } from "../../test/accessibility";
import { Button } from "./Button";

test("uses a non-submitting button type by default", () => {
    render(<Button>Retry status</Button>);

    expect(
        screen.getByRole("button", { name: "Retry status" }),
    ).toHaveAttribute("type", "button");
});

test("allows submit buttons and disabled actions", () => {
    render(
        <Button disabled type="submit" variant="primary">
            Upload document
        </Button>,
    );

    expect(
        screen.getByRole("button", { name: "Upload document" }),
    ).toBeDisabled();
    expect(
        screen.getByRole("button", { name: "Upload document" }),
    ).toHaveAttribute("type", "submit");
});

test("has no detectable accessibility violations", async () => {
    const { container } = render(
        <Button variant="danger">Reject document</Button>,
    );

    expect((await axe(container)).violations).toEqual([]);
});
