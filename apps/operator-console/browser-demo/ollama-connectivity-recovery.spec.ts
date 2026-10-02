import { expect, test, type Page } from "@playwright/test";

import type { DocumentStatus } from "../src/api/documentApi";

test("provider outage leaves review available and recovery restores proposals", async ({
    page,
}, testInfo) => {
    const failedUrl = process.env.DEMO_FAILED_DOCUMENT_URL;
    const recoveredUrl = process.env.DEMO_RECOVERED_DOCUMENT_URL;
    if (!failedUrl || !recoveredUrl) {
        throw new Error(
            "Set DEMO_FAILED_DOCUMENT_URL and DEMO_RECOVERED_DOCUMENT_URL to local console URLs",
        );
    }

    const failed = await readDocument(page, failedUrl);
    expect(failed.status).toBe("REVIEW_REQUIRED");
    expect(failed.current_run.status).toBe("REVIEW_REQUIRED");
    expect(failed.current_run.ai_execution?.status).toBe("FAILED");
    expect(failed.current_run.ai_proposal_failure?.code).toBe("UNAVAILABLE");
    expect(failed.current_run.ai_proposal).toBeNull();
    expect(failed.current_run.review_resolution).toBeNull();
    expect(
        failed.current_run.processing_output?.invoice_validation?.decision,
    ).toBe("REVIEW_REQUIRED");

    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    await page.goto(failedUrl);
    await expect(
        page.getByText("Action required: review this document"),
    ).toBeVisible();
    await expect(
        page.getByText("AI proposal unavailable: Unavailable."),
    ).toBeVisible();
    await expect(
        page.getByRole("button", { name: "Approve document" }),
    ).toBeVisible();
    await page.screenshot({
        path: testInfo.outputPath("ollama-unavailable-review.png"),
        fullPage: true,
    });

    const recovered = await readDocument(page, recoveredUrl);
    expect(recovered.status).toBe("REVIEW_REQUIRED");
    expect(recovered.current_run.ai_execution?.status).toBe("COMPLETED");
    expect(recovered.current_run.ai_proposal_failure).toBeNull();
    expect(recovered.current_run.ai_proposal?.status).toBe("VALID");
    expect(recovered.current_run.ai_proposal?.currency).toBe("CAD");
    expect(recovered.current_run.ai_proposal?.total_amount).toBe("99.0000");
    expect(recovered.current_run.review_resolution).toBeNull();

    await page.goto(recoveredUrl);
    await expect(
        page.getByText("Action required: review this document"),
    ).toBeVisible();
    await expect(page.getByText("AI proposal comparison")).toBeVisible();
    await expect(
        page.getByText("Execution completed", { exact: true }),
    ).toBeVisible();
    await expect(
        page.getByText("AI proposal unavailable: Unavailable."),
    ).toHaveCount(0);
    await page.screenshot({
        path: testInfo.outputPath("ollama-recovered-review.png"),
        fullPage: true,
    });
    expect(browserErrors).toEqual([]);
});

async function readDocument(
    page: Page,
    documentUrl: string,
): Promise<DocumentStatus> {
    const url = new URL(documentUrl);
    const documentId = url.searchParams.get("documentId");
    if (!documentId) throw new Error("Each demo URL must include documentId");
    const response = await page.request.get(
        new URL(`/api/v1/documents/${documentId}`, url).toString(),
    );
    expect(response.ok()).toBe(true);
    return (await response.json()) as DocumentStatus;
}
