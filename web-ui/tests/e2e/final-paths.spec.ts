import { expect, test } from "@playwright/test";

test("final core paths: settings patch, seedbox manage, upload toggle, pipeline and batch validations", async ({ page }) => {
  const seedboxes: Array<{
    name: string;
    rclone_remote: string;
    remote_base_path: string;
    max_concurrent_uploads: number;
    bandwidth_limit: string;
    is_default: boolean;
  }> = [
    {
      name: "main-seedbox",
      rclone_remote: "main",
      remote_base_path: "/downloads",
      max_concurrent_uploads: 3,
      bandwidth_limit: "",
      is_default: true,
    },
  ];

  await page.route("http://127.0.0.1:8000/api/v1/settings/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        settings_path: "C:/cfg/framekit.yaml",
        config_dir: "C:/cfg",
        cache_dir: "C:/cache",
        settings: { general: { locale: "fr" }, seedbox: { max_concurrent_uploads: 3 } },
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/settings/patch", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        settings_path: "C:/cfg/framekit.yaml",
        config_dir: "C:/cfg",
        cache_dir: "C:/cache",
        settings: { general: { locale: "en" }, seedbox: { max_concurrent_uploads: 5 } },
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/seedbox/list", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ seedboxes }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/seedbox/add", async (route) => {
    const body = route.request().postDataJSON() as {
      name: string;
      rclone_remote: string;
      remote_base_path: string;
      max_concurrent_uploads: number;
    };
    seedboxes.push({
      name: body.name,
      rclone_remote: body.rclone_remote,
      remote_base_path: body.remote_base_path,
      max_concurrent_uploads: body.max_concurrent_uploads,
      bandwidth_limit: "",
      is_default: false,
    });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ seedboxes }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/seedbox/use", async (route) => {
    const body = route.request().postDataJSON() as { name: string };
    for (const item of seedboxes) {
      item.is_default = item.name === body.name;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ seedboxes }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/seedbox/remove", async (route) => {
    const body = route.request().postDataJSON() as { name: string };
    const next = seedboxes.filter((item) => item.name !== body.name);
    seedboxes.length = 0;
    seedboxes.push(...next);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ seedboxes }),
    });
  });

  await page.route(/http:\/\/127\.0\.0\.1:8000\/api\/v1\/seedbox\/history.*/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ entries: [{ seedbox: "main-seedbox", action: "push", success: true }] }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/trackers", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        trackers: [{ name: "bhd", type: "unit3d", url: "https://tracker.example", enabled: true }],
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/tracker/bhd", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tracker: { name: "bhd", type: "unit3d", url: "https://tracker.example", token_env: "BHD_TOKEN" },
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/state", async (route) => {
    if (route.request().method().toUpperCase() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: true, auto_upload: false }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled: false, auto_upload: false }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/history?limit=20", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ entries: [{ tracker: "bhd", success: true }] }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/modules/run", async (route) => {
    const body = route.request().postDataJSON() as { module: string };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        argv: ["python", "-m", "framekit", body.module],
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
          id: "job-final-1",
          status: "pending",
          created_at: new Date().toISOString(),
          request: { module: "pipeline" },
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
  await page.getByRole("button", { name: "Appliquer patch" }).click();
  await expect(page.getByText("C:/cfg/framekit.yaml")).toBeVisible();

  await page.goto("/seedbox");
  await page.getByLabel("Name").fill("edge-seed");
  await page.getByLabel("rclone remote").fill("edge-remote");
  await page.getByLabel("remote base path").fill("/edge");
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText("edge-seed")).toBeVisible();
  await page.getByRole("button", { name: "Use default" }).click();
  await page.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByText("edge-seed")).toHaveCount(0);

  await page.goto("/upload");
  await page.getByRole("button", { name: "bhd" }).click();
  await expect(page.getByText("BHD_TOKEN")).toBeVisible();
  await page.getByRole("button", { name: "Toggle enabled" }).click();
  await expect(page.getByText("Upload enabled:")).toBeVisible();

  await page.goto("/pipeline");
  await page.getByLabel("Arguments").fill("");
  await page.getByRole("button", { name: "Exécuter" }).click();
  await expect(page.getByText("Les arguments pipeline sont requis.")).toBeVisible();
  await page.getByRole("button", { name: "Movie Core" }).click();
  await page.getByRole("button", { name: "Exécuter" }).click();
  await expect(page.getByRole("button", { name: "Ouvrir dernier job" })).toBeVisible();

  await page.goto("/batch");
  await page.getByLabel("Arguments").fill("");
  await page.getByRole("button", { name: "Exécuter" }).click();
  await expect(page.getByText("Les arguments batch sont requis.")).toBeVisible();
  await page.getByRole("button", { name: "Scan dossier" }).click();
  await page.getByRole("button", { name: "Exécuter" }).click();
  await expect(page.getByRole("button", { name: "Ouvrir dernier job" })).toBeVisible();
});
