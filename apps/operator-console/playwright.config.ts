import { defineConfig } from "@playwright/test";

export default defineConfig({
    testDir: "./tests",
    outputDir: "./test-results",
    reporter: "line",
    use: {
        baseURL: "http://127.0.0.1:6006",
        trace: "retain-on-failure",
    },
    webServer: {
        command: "pnpm exec storybook dev --port 6006 --ci",
        port: 6006,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
    },
});
