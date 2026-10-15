import { expect, test } from "@playwright/test";

import type { DocumentStatus } from "../src/api/documentApi";

test("unrelated report finishes as unsupported without invoice review", async ({
    page,
}, testInfo) => {
    const documentUrl = process.env.DEMO_DOCUMENT_URL;
    if (!documentUrl || !new URL(documentUrl).searchParams.has("documentId")) {
        throw new Error(
            "Set DEMO_DOCUMENT_URL to an equipment-report console URL",
        );
    }

    const documentId = new URL(documentUrl).searchParams.get("documentId")!;
    const statusUrl = new URL(`/api/v1/documents/${documentId}`, documentUrl);
    const response = await page.request.get(statusUrl.toString());
    expect(response.ok()).toBe(true);
    const document = (await response.json()) as DocumentStatus;
    expect(document.original_filename).toBe("equipment-report.pdf");
    expect(document.status).toBe("UNSUPPORTED");
    expect(document.current_run.status).toBe("COMPLETED");
    expect(document.current_run.processing_output?.embedded_text?.quality).toBe(
        "SUFFICIENT",
    );
    expect(document.current_run.processing_output?.ocr_text).toBeNull();
    expect(document.current_run.processing_output?.selected_text?.source).toBe(
        "EMBEDDED",
    );
    expect(
        document.current_run.processing_output?.classification,
    ).toMatchObject({
        document_type: "UNKNOWN",
        reason: "NO_MATCH",
    });
    expect(
        document.current_run.processing_output?.invoice_extraction,
    ).toBeNull();
    expect(
        document.current_run.processing_output?.invoice_validation,
    ).toBeNull();
    expect(document.current_run.ai_execution).toBeNull();
    expect(document.current_run.ai_proposal).toBeNull();
    expect(document.current_run.review_resolution).toBeNull();

    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    const loadedStatus = page.waitForResponse(
        (response) => response.url() === statusUrl.toString(),
    );
    await page.goto(documentUrl);
    expect((await loadedStatus).status()).toBe(200);
    await expect(
        page.getByText(
            "The document type could not be recognized. No structured extraction was performed.",
        ),
    ).toBeVisible();
    await expect(page.getByText("equipment-report.pdf")).toBeVisible();
    await page
        .getByText("Processing results and AI details", { exact: true })
        .click();
    await expect(page.getByText("No Match")).toBeVisible();
    await expect(
        page.getByRole("button", { name: "Approve document" }),
    ).toHaveCount(0);
    await expect(
        page.getByRole("button", { name: "Reject document" }),
    ).toHaveCount(0);
    await expect(page.getByText("Request controlled reprocessing")).toHaveCount(
        0,
    );
    await page.screenshot({
        path: testInfo.outputPath("unrelated-report-details.png"),
        fullPage: true,
    });

    await page.getByRole("button", { name: "Back to work queues" }).click();
    await page
        .getByRole("button", { name: "Unsupported", exact: true })
        .click();
    await expect(page.getByText(documentId)).toBeVisible();
    const row = page.getByText(documentId).locator("..");
    await expect(row.getByText("equipment-report.pdf")).toBeVisible();
    await expect(page.getByText("No unsupported documents found.")).toHaveCount(
        0,
    );
    await row.getByRole("button", { name: "View details" }).click();
    await expect(
        page.getByRole("region", { name: "equipment-report.pdf" }),
    ).toBeVisible();
    await page.screenshot({
        path: testInfo.outputPath("unrelated-report-workspace.png"),
        fullPage: true,
    });
    expect(browserErrors).toEqual([]);
});
