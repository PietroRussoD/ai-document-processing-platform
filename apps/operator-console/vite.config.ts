import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
    plugins: [react(), tailwindcss()],
    server: {
        proxy: {
            "/api": {
                target:
                    process.env.VITE_API_PROXY_TARGET ??
                    "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
    test: {
        environment: "jsdom",
        setupFiles: ["./src/test/setup.ts"],
        coverage: {
            provider: "v8",
            reporter: ["text", "json-summary", "html"],
            reportsDirectory: "./coverage",
            include: ["src/**/*.{ts,tsx}"],
            exclude: ["src/main.tsx", "src/test/**", "**/*.test.{ts,tsx}"],
            thresholds: {
                statements: 80,
                branches: 80,
                functions: 75,
                lines: 80,
            },
        },
    },
});
