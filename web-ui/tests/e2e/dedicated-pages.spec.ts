import { expect, test } from "@playwright/test";

test("dedicated pages render and execute mocked commands", async ({ page }) => {
  await page.route("http://127.0.0.1:8000/api/v1/settings/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        settings_path: "C:/cfg/framekit.yaml",
        config_dir: "C:/cfg",
        cache_dir: "C:/cache",
        settings: { general: { locale: "fr" } },
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/seedbox/list", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        seedboxes: [
          {
            name: "main-seedbox",
            rclone_remote: "main",
            remote_base_path: "/downloads",
            max_concurrent_uploads: 3,
            bandwidth_limit: "",
            is_default: true,
          },
        ],
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/trackers", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        trackers: [
          { name: "bhd", type: "unit3d", url: "https://tracker.example", enabled: true },
        ],
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/modules/run", async (route) => {
    const req = route.request();
    const body = req.postDataJSON() as { module: string; args_text: string };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        argv: ["python", "-m", "framekit", body.module, ...body.args_text.split(" ").filter(Boolean)],
        returncode: 0,
        stdout: `ran ${body.module}`,
        stderr: "",
        parsed_kind: null,
        parsed_payload: null,
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/modules/jobs", async (route) => {
    if (route.request().method().toUpperCase() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "job-studio-1",
          status: "pending",
          created_at: new Date().toISOString(),
          request: { module: "watch" },
          live_stdout: "",
          live_stderr: "",
          result: null,
          error: null,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    });
  });

  await page.goto("/settings-setup");
  await expect(page.getByRole("heading", { name: "Settings & Setup" })).toBeVisible();
  await expect(page.getByText("main-seedbox")).toBeVisible();
  await expect(page.getByText("bhd")).toBeVisible();

  await page.goto("/seedbox");
  await page.getByRole("button", { name: "Exécuter" }).click();
  await expect(page.getByText("ran seedbox")).toBeVisible();

  await page.goto("/upload");
  await page.getByRole("button", { name: "Exécuter" }).click();
  await expect(page.getByText("ran upload")).toBeVisible();

  await page.goto("/studio/watch");
  await expect(page.getByRole("heading", { name: /Module Studio/ })).toBeVisible();
  await page.getByRole("button", { name: "Exécuter" }).click();
  await expect(page.getByRole("button", { name: "Ouvrir dernier job" })).toBeVisible();
});
