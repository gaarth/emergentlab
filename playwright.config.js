// Viewer tests: npx playwright test   (starts python -m http.server 8000 unless one is already running)
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests",
  testMatch: /.*\.spec\.js/,
  timeout: 30000,
  fullyParallel: true,
  workers: 4,
  reporter: "list",
  use: { baseURL: "http://localhost:8000", browserName: "chromium" },
  webServer: { command: "python -m http.server 8000", url: "http://localhost:8000/viewer.html", reuseExistingServer: true,
               stdout: "ignore", stderr: "ignore" },
});
