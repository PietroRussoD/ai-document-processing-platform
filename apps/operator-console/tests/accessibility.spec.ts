import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const approvedReviewStory =
    "/iframe.html?id=document-review-resolvedreview--approved&viewMode=story";
const rejectedReviewStory =
    "/iframe.html?id=document-review-resolvedreview--rejected-without-note&viewMode=story";
const reviewResolutionFormStory =
    "/iframe.html?id=document-review-reviewresolutionform--ready&viewMode=story";
const documentReprocessingStory =
    "/iframe.html?id=document-reprocessing-documentreprocessingpanel--ready&viewMode=story";
const documentWorkQueuesStory =
    "/iframe.html?id=document-work-queues-documentworkqueuespanel--active-queue&viewMode=story";
const feedbackMessageStory =
    "/iframe.html?id=ui-feedbackmessage--warning&viewMode=story";
const primaryButtonStory = "/iframe.html?id=ui-button--primary&viewMode=story";
const aiComparisonStory =
    "/iframe.html?id=processing-output-aiinvoicecomparison--partial-proposal&viewMode=story";

for (const width of [1440, 320]) {
    for (const story of [
        "with-source-pdf",
        "loading-source-pdf",
        "source-pdf-failure",
    ]) {
        test(`Source review ${story} is accessible and fits ${width}px`, async ({
            page,
        }, testInfo) => {
            await page.setViewportSize({ width, height: 1000 });
            await page.goto(
                `/iframe.html?id=document-review-reviewresolutionform--${story}&viewMode=story`,
            );
            const openButton = page.getByRole("button", {
                name: "View source PDF",
            });
            await expect(openButton).toBeDisabled();
            await expect(page.getByTitle("Source PDF preview")).toHaveCount(0);
            await page.getByLabel("Operator token").fill("storybook-token");
            if (story === "with-source-pdf") {
                const responsePromise = page.waitForResponse((response) =>
                    response.url().endsWith("/fixtures/invoice-digital.pdf"),
                );
                await openButton.click();
                const response = await responsePromise;
                expect(response.ok()).toBe(true);
                expect(response.headers()["content-type"]).toContain(
                    "application/pdf",
                );
                await expect(
                    page.getByTitle("Source PDF preview"),
                ).toBeVisible();
                const pdfHeader = await page
                    .getByTitle("Source PDF preview")
                    .evaluate(async (element) => {
                        const previewResponse = await fetch(
                            (element as HTMLIFrameElement).src,
                        );
                        return (await previewResponse.text()).slice(0, 4);
                    });
                expect(pdfHeader).toBe("%PDF");
                await expect(
                    page.getByRole("link", { name: "Open PDF in new tab" }),
                ).toHaveAttribute("href", /^blob:/);
            } else {
                await openButton.click();
                if (story === "loading-source-pdf") {
                    await expect(
                        page.getByRole("button", {
                            name: "Loading source PDF",
                        }),
                    ).toBeDisabled();
                } else {
                    await expect(page.getByRole("alert")).toHaveText(
                        "The source PDF could not be loaded.",
                    );
                    await expect(openButton).toBeEnabled();
                }
            }
            const source = await page
                .getByRole("heading", { name: "Original source document" })
                .locator("..")
                .boundingBox();
            const corrections = await page
                .getByRole("group", {
                    name: "Correct extracted invoice fields",
                })
                .boundingBox();
            expect(source).not.toBeNull();
            expect(corrections).not.toBeNull();
            if (width === 1440) {
                expect(corrections!.x).toBeGreaterThanOrEqual(
                    source!.x + source!.width,
                );
            } else {
                expect(corrections!.y).toBeGreaterThanOrEqual(
                    source!.y + source!.height,
                );
            }
            const results = await new AxeBuilder({ page })
                .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
                .disableRules(["landmark-one-main", "page-has-heading-one"])
                .analyze();
            expect(results.violations).toEqual([]);
            expect(
                await page.evaluate(
                    () =>
                        document.documentElement.scrollWidth >
                        window.innerWidth,
                ),
            ).toBe(false);
            await page.screenshot({
                path: testInfo.outputPath(`review-${story}-${width}.png`),
                fullPage: true,
            });
            if (story === "with-source-pdf") {
                await page
                    .getByRole("button", { name: "Close source PDF" })
                    .click();
                await expect(page.getByTitle("Source PDF preview")).toHaveCount(
                    0,
                );
                await expect(
                    page.getByRole("link", { name: "Open PDF in new tab" }),
                ).toHaveCount(0);
                await expect(page.getByLabel("Invoice number")).toHaveValue(
                    "DEMO-INV-1001",
                );
            }
        });
    }
}

test("Source review stays stacked in a narrow desktop container", async ({
    page,
}) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(
        "/iframe.html?id=document-review-reviewresolutionform--with-source-pdf&viewMode=story",
    );
    const heading = page.getByRole("heading", {
        name: "Resolve operator review",
    });
    await expect(heading).toBeVisible();
    await heading.locator("xpath=ancestor::section").evaluate((element) => {
        (element as HTMLElement).style.width = "620px";
    });
    const source = await page
        .getByRole("heading", { name: "Original source document" })
        .boundingBox();
    const corrections = await page
        .getByRole("group", { name: "Correct extracted invoice fields" })
        .boundingBox();
    expect(corrections!.y).toBeGreaterThan(source!.y);
    expect(corrections!.x).toBe(source!.x);
});

for (const width of [1440, 320]) {
    for (const story of [
        "running",
        "disabled",
        "failed",
        "unrecorded",
        "stale-running",
    ]) {
        test(`AI timeline ${story} is accessible and fits ${width}px`, async ({
            page,
        }, testInfo) => {
            await page.setViewportSize({ width, height: 900 });
            await page.goto(
                `/iframe.html?id=processing-output-processingtimeline--${story}&viewMode=story`,
            );
            await expect(
                page.getByText("Advisory AI proposal", { exact: true }),
            ).toBeVisible();
            await expect(
                page.getByText(
                    "Deterministic processing finished; operator review is required.",
                ),
            ).toBeVisible();
            const results = await new AxeBuilder({ page })
                .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
                .disableRules(["landmark-one-main", "page-has-heading-one"])
                .analyze();
            expect(results.violations).toEqual([]);
            expect(
                await page.evaluate(
                    () =>
                        document.documentElement.scrollWidth >
                        window.innerWidth,
                ),
            ).toBe(false);
            await page.screenshot({
                path: testInfo.outputPath(`timeline-${story}-${width}.png`),
                fullPage: true,
            });
        });
    }
}

for (const width of [1440, 320]) {
    for (const [story, message] of [
        ["running", "AI proposal pending."],
        ["disabled", "AI proposals are disabled for this run."],
        ["unrecorded", "AI execution state is not recorded."],
        [
            "stale-running",
            "AI execution still reports running; automatic updates are paused.",
        ],
    ]) {
        test(`AI execution ${story} is accessible and fits ${width}px`, async ({
            page,
        }, testInfo) => {
            await page.setViewportSize({ width, height: 900 });
            await page.goto(
                `/iframe.html?id=processing-output-aiinvoicecomparison--${story}&viewMode=story`,
            );
            await expect(page.getByText(message)).toBeVisible();
            const results = await new AxeBuilder({ page })
                .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
                .disableRules(["landmark-one-main", "page-has-heading-one"])
                .analyze();
            expect(results.violations).toEqual([]);
            expect(
                await page.evaluate(
                    () =>
                        document.documentElement.scrollWidth >
                        window.innerWidth,
                ),
            ).toBe(false);
            await page.screenshot({
                path: testInfo.outputPath(`ai-${story}-${width}.png`),
                fullPage: true,
            });
        });
    }
}

test("AI comparison has no browser-detected accessibility violations", async ({
    page,
}) => {
    await page.goto(aiComparisonStory);
    await expect(
        page.getByRole("heading", { name: "AI proposal comparison" }),
    ).toBeVisible();

    const results = await new AxeBuilder({ page })
        .disableRules(["landmark-one-main", "page-has-heading-one"])
        .analyze();

    expect(results.violations).toEqual([]);
});

test("AI comparison fits a narrow viewport", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 720 });
    await page.goto(aiComparisonStory);
    await expect(
        page.getByRole("heading", { name: "AI proposal comparison" }),
    ).toBeVisible();

    const hasHorizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
    );

    expect(hasHorizontalOverflow).toBe(false);
});

test("approved review outcome has no browser-detected accessibility violations", async ({
    page,
}) => {
    await page.goto(approvedReviewStory);
    await expect(
        page.getByRole("heading", { name: "Review resolved" }),
    ).toBeVisible();

    const results = await new AxeBuilder({ page })
        .disableRules(["landmark-one-main", "page-has-heading-one"])
        .analyze();

    expect(results.violations).toEqual([]);
});

test("rejected review outcome fits a narrow viewport", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 720 });
    await page.goto(rejectedReviewStory);
    await expect(
        page.getByRole("heading", { name: "Review resolved" }),
    ).toBeVisible();

    const hasHorizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
    );

    expect(hasHorizontalOverflow).toBe(false);
});

test("review resolution form has no browser-detected accessibility violations", async ({
    page,
}) => {
    await page.goto(reviewResolutionFormStory);
    await expect(
        page.getByRole("heading", { name: "Resolve operator review" }),
    ).toBeVisible();

    const results = await new AxeBuilder({ page })
        .disableRules(["landmark-one-main", "page-has-heading-one"])
        .analyze();

    expect(results.violations).toEqual([]);
});

test("document reprocessing form has no browser-detected accessibility violations", async ({
    page,
}) => {
    await page.goto(documentReprocessingStory);
    await expect(
        page.getByRole("heading", { name: "Request controlled reprocessing" }),
    ).toBeVisible();

    const results = await new AxeBuilder({ page })
        .disableRules(["landmark-one-main", "page-has-heading-one"])
        .analyze();

    expect(results.violations).toEqual([]);
});

test("document work queues have no browser-detected accessibility violations", async ({
    page,
}) => {
    await page.goto(documentWorkQueuesStory);
    await expect(
        page.getByRole("heading", { name: "Document work queues" }),
    ).toBeVisible();
    await expect(page.getByText("supplier-invoice-1042.pdf")).toBeVisible();

    const results = await new AxeBuilder({ page })
        .disableRules(["landmark-one-main", "page-has-heading-one"])
        .analyze();

    expect(results.violations).toEqual([]);
});

test("document work queues fit a narrow viewport", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 720 });
    await page.goto(documentWorkQueuesStory);
    await expect(
        page.getByRole("heading", { name: "Document work queues" }),
    ).toBeVisible();

    const hasHorizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
    );

    expect(hasHorizontalOverflow).toBe(false);
});

test("feedback message has no browser-detected accessibility violations", async ({
    page,
}) => {
    await page.goto(feedbackMessageStory);
    await expect(
        page.getByText("Processing requires an operator review."),
    ).toBeVisible();

    const results = await new AxeBuilder({ page })
        .disableRules(["landmark-one-main", "page-has-heading-one"])
        .analyze();

    expect(results.violations).toEqual([]);
});

test("primary button has no browser-detected accessibility violations", async ({
    page,
}) => {
    await page.goto(primaryButtonStory);
    await expect(
        page.getByRole("button", { name: "Upload document" }),
    ).toBeVisible();

    const results = await new AxeBuilder({ page })
        .disableRules(["landmark-one-main", "page-has-heading-one"])
        .analyze();

    expect(results.violations).toEqual([]);
});
