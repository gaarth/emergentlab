// UI tests: (cd app && npm run build) then `npx playwright test`. Starts server.py on 8000 unless one is already running.
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests",
  testMatch: /app\.spec\.js/,
  timeout: 40000,
  fullyParallel: true,
  workers: 3,
  reporter: "list",
  use: {
    baseURL: "http://localhost:8000",
    browserName: "chromium",
    launchOptions: { args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"] },
  },
  webServer: { command: "python server.py", url: "http://localhost:8000/api/status", reuseExistingServer: true, stdout: "ignore", stderr: "ignore" },
});
