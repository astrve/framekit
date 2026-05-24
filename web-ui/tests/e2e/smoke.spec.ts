import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("home and doctor screens render with mocked API", async ({ page }) => {
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
        name: "framekit",
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

  await page.goto("/");
  await expect(page.getByText("Framekit stack must")).toBeVisible();

  await page.goto("/doctor");
  await expect(page.getByText("Doctor summary")).toBeVisible();
  await expect(page.getByText("ok: 2")).toBeVisible();

  const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
  expect(accessibilityScanResults.violations).toEqual([]);
});

