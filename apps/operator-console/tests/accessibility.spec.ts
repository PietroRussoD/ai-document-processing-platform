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
