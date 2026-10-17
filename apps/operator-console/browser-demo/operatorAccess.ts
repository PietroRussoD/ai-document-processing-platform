import { expect, type Page } from "@playwright/test";

export function operatorHeaders() {
    const token = process.env.DEMO_REVIEW_TOKEN;
    if (!token)
        throw new Error("Set DEMO_REVIEW_TOKEN to the local operator token");
    return { Authorization: `Bearer ${token}` };
}

export async function openDocumentsWithOperatorToken(page: Page) {
    const token = process.env.DEMO_REVIEW_TOKEN;
    if (!token)
        throw new Error("Set DEMO_REVIEW_TOKEN to the local operator token");
    await page.getByLabel("Operator token").fill(token);
    await page.getByRole("button", { name: "Open documents" }).click();
    await expect(page.getByText("Operator token accepted.")).toBeVisible();
}
