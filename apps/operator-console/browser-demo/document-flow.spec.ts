import { expect, test } from "@playwright/test";
import { openDocumentsWithOperatorToken } from "./operatorAccess";

test("synthetic document remains inspectable across console views", async ({
    page,
}, testInfo) => {
    const documentUrl = process.env.DEMO_DOCUMENT_URL;
    if (!documentUrl || !new URL(documentUrl).searchParams.has("documentId")) {
        throw new Error(
            "Set DEMO_DOCUMENT_URL to the Console document URL printed by the Compose smoke test",
        );
    }

    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    page.on("console", (message) => {
        if (message.type() === "error") browserErrors.push(message.text());
    });

    await page.goto(documentUrl);
    await openDocumentsWithOperatorToken(page);
    await expect(
        page.getByText("Action required: review this document"),
    ).toBeVisible();
    await expect(
        page
            .getByRole("list", { name: "Reasons for review" })
            .getByText("Missing Invoice Number", { exact: true }),
    ).toBeVisible();
    await page.screenshot({
        path: testInfo.outputPath("document.png"),
        fullPage: true,
    });
    expect(await hasHorizontalOverflow(page)).toBe(false);

    await page.getByText("Browse work queues", { exact: true }).click();
    await page.getByRole("button", { name: "Needs review" }).click();
    await expect(
        page
            .getByRole("region", { name: "Document work queues" })
            .getByText(new URL(documentUrl).searchParams.get("documentId")!, {
                exact: true,
            })
            .locator("..")
            .getByText("compose-smoke.pdf"),
    ).toBeVisible();
    await page.getByRole("link", { name: "System Map" }).click();
    await expect(
        page.getByRole("heading", { name: "System Map" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Review-required invoice" }).click();
    await expect(
        page.getByRole("button", { name: /Resolve review/ }),
    ).toBeVisible();
    await page.evaluate(() => {
        if (document.activeElement instanceof HTMLElement)
            document.activeElement.blur();
        window.scrollTo(0, 0);
    });
    await page.screenshot({
        path: testInfo.outputPath("system-map.png"),
        fullPage: true,
    });

    expect(await hasHorizontalOverflow(page)).toBe(false);
    expect(browserErrors).toEqual([]);
});

async function hasHorizontalOverflow(
    page: import("@playwright/test").Page,
): Promise<boolean> {
    return page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
    );
}
