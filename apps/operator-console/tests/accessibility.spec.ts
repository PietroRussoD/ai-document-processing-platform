import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const approvedReviewStory =
    "/iframe.html?id=document-review-resolvedreview--approved&viewMode=story";
const rejectedReviewStory =
    "/iframe.html?id=document-review-resolvedreview--rejected-without-note&viewMode=story";
const reviewResolutionFormStory =
    "/iframe.html?id=document-review-reviewresolutionform--ready&viewMode=story";

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
