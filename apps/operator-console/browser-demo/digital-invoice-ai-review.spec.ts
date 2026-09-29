import { expect, test } from "@playwright/test";

import type { DocumentStatus } from "../src/api/documentApi";

test("digital invoice AI proposal remains advisory until operator approval", async ({
    page,
}, testInfo) => {
    const documentUrl = process.env.DEMO_DOCUMENT_URL;
    const operatorToken = process.env.DEMO_REVIEW_TOKEN;
    if (!documentUrl || !new URL(documentUrl).searchParams.has("documentId")) {
        throw new Error(
            "Set DEMO_DOCUMENT_URL to a digital-invoice console URL",
        );
    }
    if (!operatorToken) {
        throw new Error("Set DEMO_REVIEW_TOKEN to the local review token");
    }

    const documentId = new URL(documentUrl).searchParams.get("documentId")!;
    const statusUrl = new URL(`/api/v1/documents/${documentId}`, documentUrl);
    const beforeResponse = await page.request.get(statusUrl.toString());
    expect(beforeResponse.ok()).toBe(true);
    const before = (await beforeResponse.json()) as DocumentStatus;
    expect(before.status).toBe("REVIEW_REQUIRED");
    expect(before.current_run.ai_execution?.status).toBe("COMPLETED");
    expect(before.current_run.ai_proposal?.status).toBe("VALID");
    expect(before.current_run.ai_proposal?.currency).toBe("CAD");
    expect(before.current_run.ai_proposal?.total_amount).toBe("99.0000");
    expect(
        before.current_run.processing_output?.invoice_extraction?.currency,
    ).toBeNull();
    expect(
        before.current_run.processing_output?.invoice_extraction?.total_amount,
    ).toBeNull();

    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    await page.goto(documentUrl);
    await expect(
        page.getByText("Processing requires an operator review."),
    ).toBeVisible();
    await expect(
        page.getByText(
            "AI execution completed; proposal validity and document approval are separate.",
        ),
    ).toBeVisible();
    await page.getByLabel("Operator token").fill(operatorToken);

    const sourceResponse = page.waitForResponse((response) =>
        response.url().endsWith(`/api/v1/documents/${documentId}/source`),
    );
    await page.getByRole("button", { name: "View source PDF" }).click();
    const pdf = await sourceResponse;
    expect(pdf.status()).toBe(200);
    expect(pdf.headers()["content-type"]).toContain("application/pdf");
    expect(pdf.headers()["cache-control"]).toContain("no-store");
    await expect(page.getByTitle("Source PDF preview")).toBeVisible();
    await page.screenshot({
        path: testInfo.outputPath("digital-invoice-before-review.png"),
        fullPage: true,
    });

    await page
        .getByRole("button", { name: "Use AI proposal for Currency" })
        .click();
    await page
        .getByRole("button", { name: "Use AI proposal for Total amount" })
        .click();
    await expect(page.getByRole("textbox", { name: "Currency" })).toHaveValue(
        "CAD",
    );
    await expect(
        page.getByRole("spinbutton", { name: "Total amount" }),
    ).toHaveValue("99.0000");
    await page.getByRole("button", { name: "Approve document" }).click();

    await expect
        .poll(async () => {
            const response = await page.request.get(statusUrl.toString());
            expect(response.ok()).toBe(true);
            return ((await response.json()) as DocumentStatus).status;
        })
        .toBe("APPROVED");
    const after = (await (
        await page.request.get(statusUrl.toString())
    ).json()) as DocumentStatus;
    expect(after.current_run.review_resolution?.decision).toBe("APPROVE");
    expect(after.current_run.review_resolution?.corrections).toMatchObject([
        { field: "CURRENCY", corrected_value: "CAD", source: "AI_PROPOSAL" },
        {
            field: "TOTAL_AMOUNT",
            corrected_value: "99.0000",
            source: "AI_PROPOSAL",
        },
    ]);
    for (const correction of after.current_run.review_resolution?.corrections ??
        []) {
        expect(Number.isNaN(Date.parse(correction.corrected_at))).toBe(false);
    }
    expect(
        after.current_run.processing_output?.invoice_extraction?.currency,
    ).toBeNull();
    expect(
        after.current_run.processing_output?.invoice_extraction?.total_amount,
    ).toBeNull();
    expect(after.current_run.ai_proposal?.currency).toBe("CAD");
    expect(after.current_run.ai_proposal?.total_amount).toBe("99.0000");
    await expect(page.getByText("Processing results are ready.")).toBeVisible();
    await page.screenshot({
        path: testInfo.outputPath("digital-invoice-approved.png"),
        fullPage: true,
    });
    expect(browserErrors).toEqual([]);
});
