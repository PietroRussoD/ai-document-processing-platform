import { defineConfig } from "@playwright/test";

export default defineConfig({
    testDir: "./browser-demo",
    outputDir: "./test-results/demo",
    reporter: "line",
    use: {
        browserName: "chromium",
        channel: "chromium",
        trace: "retain-on-failure",
    },
    projects: [
        {
            name: "desktop",
            use: { viewport: { width: 1440, height: 900 } },
        },
        {
            name: "mobile",
            use: {
                viewport: { width: 390, height: 844 },
                isMobile: true,
                hasTouch: true,
            },
        },
    ],
});
