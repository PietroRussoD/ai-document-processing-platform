import { render } from "@testing-library/react";
import { expect, test } from "vitest";

import { axe } from "../../test/accessibility";
import { StatusBadge } from "./StatusBadge";

test("has no detectable accessibility violations", async () => {
    const { container } = render(
        <StatusBadge label="Review required" tone="warning" />,
    );

    expect((await axe(container)).violations).toEqual([]);
});
