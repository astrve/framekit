import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function mockShell(page: import("@playwright/test").Page) {
  await page.route("http://127.0.0.1:8000/api/v1/auth/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        enabled: false,
        has_users: false,
        user_count: 0,
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/profiles", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        profiles: [],
        active: null,
      }),
    });
  });
}

test("home and doctor screens render with mocked API", async ({ page }) => {
  await mockShell(page);

  await page.route("http://127.0.0.1:8000/healthz", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/system/info", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        name: "swirrl",
        version: "2.0.0",
        python_version: "3.12.0",
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/doctor", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tools: [{ name: "ffmpeg", found: true }],
        checks: [
          { section: "Runtime", name: "python", status: "ok", detail: "3.12" },
          { section: "Tools", name: "ffmpeg", status: "ok", detail: "found" },
        ],
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/modules/jobs?limit=100", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/state", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled: false, auto_upload: false }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/history?limit=1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ entries: [] }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/seedbox/list", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ seedboxes: [] }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/security/vault", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        enabled: true,
        vault_exists: true,
        key_exists: true,
        entry_count: 0,
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/service/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "running",
        pid: 1234,
        started_at: null,
        heartbeat_at: null,
        uptime_seconds: 120,
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/trackers", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ trackers: [] }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("Self-hosted media workflow automation")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Active Operations" })).toBeVisible();

  await page.goto("/doctor");
  await expect(page.getByRole("heading", { name: "System Diagnostics" })).toBeVisible();
  await expect(page.getByText("2 passed")).toBeVisible();
  await expect(page.getByText("0 warnings")).toBeVisible();
  await expect(page.getByText("0 errors")).toBeVisible();

  const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
  const nonContrastViolations = accessibilityScanResults.violations.filter(
    (violation) => violation.id !== "color-contrast",
  );
  const criticalViolations = accessibilityScanResults.violations.filter(
    (violation) => violation.impact === "critical",
  );
  expect(nonContrastViolations).toEqual([]);
  expect(criticalViolations).toEqual([]);
});

