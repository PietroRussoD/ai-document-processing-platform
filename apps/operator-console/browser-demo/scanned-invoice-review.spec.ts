import { expect, test } from "@playwright/test";

import type { DocumentStatus } from "../src/api/documentApi";

const reviewNote =
    "The scanned source has no invoice issue date; do not invent one.";

test("scanned invoice stays in review when OCR and AI cannot find an issue date", async ({
    page,
}, testInfo) => {
    const documentUrl = process.env.DEMO_DOCUMENT_URL;
    const operatorToken = process.env.DEMO_REVIEW_TOKEN;
    if (!documentUrl || !new URL(documentUrl).searchParams.has("documentId")) {
        throw new Error(
            "Set DEMO_DOCUMENT_URL to a scanned-invoice console URL",
        );
    }
    if (!operatorToken)
        throw new Error("Set DEMO_REVIEW_TOKEN to the local review token");

    const documentId = new URL(documentUrl).searchParams.get("documentId")!;
    const statusUrl = new URL(`/api/v1/documents/${documentId}`, documentUrl);
    const beforeResponse = await page.request.get(statusUrl.toString());
    expect(beforeResponse.ok()).toBe(true);
    const before = (await beforeResponse.json()) as DocumentStatus;
    expect(before.status).toBe("REVIEW_REQUIRED");
    expect(before.current_run.processing_output?.embedded_text?.quality).toBe(
        "OCR_RECOMMENDED",
    );
    expect(before.current_run.processing_output?.ocr_text?.method).toBe(
        "TESSERACT",
    );
    expect(before.current_run.processing_output?.selected_text?.source).toBe(
        "OCR",
    );
    expect(
        before.current_run.processing_output?.invoice_extraction
            ?.invoice_number,
    ).toBe("DEMO-INV-1002");
    expect(
        before.current_run.processing_output?.invoice_extraction?.issue_date,
    ).toBeNull();
    expect(
        before.current_run.processing_output?.invoice_extraction?.currency,
    ).toBe("EUR");
    expect(
        before.current_run.processing_output?.invoice_extraction?.total_amount,
    ).toBe("875.2500");
    expect(
        before.current_run.processing_output?.invoice_validation?.issues,
    ).toContain("MISSING_ISSUE_DATE");
    expect(before.current_run.ai_execution?.status).toBe("COMPLETED");
    expect(before.current_run.ai_proposal?.status).toBe("PARTIAL");
    expect(before.current_run.ai_proposal?.issue_date).toBeNull();
    expect(before.current_run.ai_proposal?.issues).toContainEqual({
        code: "MISSING_FIELD",
        field: "ISSUE_DATE",
    });

    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    await page.goto(documentUrl);
    await expect(
        page.getByText("Action required: review this document"),
    ).toBeVisible();
    await page.getByText("Processing history", { exact: true }).click();
    await expect(
        page.getByText("Invoice requires an operator review."),
    ).toBeVisible();
    await page.getByText("Processing history", { exact: true }).click();
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
    await expect(page.locator('input[type="date"]')).toHaveValue("");
    await page.getByLabel(/Review note/).fill(reviewNote);
    await page.screenshot({
        path: testInfo.outputPath("scanned-invoice-before-review.png"),
        fullPage: true,
    });
    await page.getByRole("button", { name: "Reject document" }).click();

    await expect
        .poll(async () => {
            const response = await page.request.get(statusUrl.toString());
            expect(response.ok()).toBe(true);
            return ((await response.json()) as DocumentStatus).status;
        })
        .toBe("REJECTED");
    const after = (await (
        await page.request.get(statusUrl.toString())
    ).json()) as DocumentStatus;
    expect(after.current_run.review_resolution?.decision).toBe("REJECT");
    expect(after.current_run.review_resolution?.review_note).toBe(reviewNote);
    expect(after.current_run.review_resolution?.corrections).toEqual([]);
    expect(
        after.current_run.processing_output?.invoice_extraction?.issue_date,
    ).toBeNull();
    expect(after.current_run.ai_proposal?.issue_date).toBeNull();
    await expect(
        page.getByText("Document rejected", { exact: true }),
    ).toBeVisible();
    await page.screenshot({
        path: testInfo.outputPath("scanned-invoice-rejected.png"),
        fullPage: true,
    });
    expect(browserErrors).toEqual([]);
});
