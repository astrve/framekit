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

test("final core paths: settings save, seedbox manage, upload toggle, pipeline and batch validation", async ({ page }) => {
  await mockShell(page);

  const resourcesPayload = {
    pipeline_presets: [{ name: "movie-core", path: "C:/cfg/pipeline/movie-core.yaml", source: "user" }],
    prez_presets: [{ name: "forum-default", path: "C:/cfg/prez/forum-default.yaml", source: "user" }],
    announces: [{ value: "https://tracker.example/announce", label: "bhd", is_selected: true }],
    selected_announce: "https://tracker.example/announce",
    nfo_templates: ["default"],
    prez_templates: { bbcode: ["classic"], html: ["aurora"] },
    banner_previews: [],
    cleanmkv_presets: ["multi"],
    renamer_profiles: ["scene"],
    encoder_presets: ["x265-fast"],
  };

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
        settings_path: "C:/cfg/swirrl.yaml",
        config_dir: "C:/cfg",
        cache_dir: "C:/cache",
        settings: { general: { locale: "en" }, seedbox: { max_concurrent_uploads: 3 } },
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/settings/patch", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        settings_path: "C:/cfg/swirrl.yaml",
        config_dir: "C:/cfg",
        cache_dir: "C:/cache",
        settings: { general: { locale: "en" }, seedbox: { max_concurrent_uploads: 5 } },
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/modules/resources", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(resourcesPayload),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/seedbox/list", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        seedboxes,
        default_by_profile: {},
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/seedbox/add", async (route) => {
    const body = route.request().postDataJSON() as {
      name: string;
      rclone_remote: string;
      remote_base_path: string;
      max_concurrent_uploads: number;
      bandwidth_limit: string;
    };
    seedboxes.push({
      name: body.name,
      rclone_remote: body.rclone_remote,
      remote_base_path: body.remote_base_path,
      max_concurrent_uploads: body.max_concurrent_uploads,
      bandwidth_limit: body.bandwidth_limit ?? "",
      is_default: false,
    });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        seedboxes,
        default_by_profile: {},
      }),
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
      body: JSON.stringify({
        seedboxes,
        default_by_profile: {},
      }),
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
      body: JSON.stringify({
        seedboxes,
        default_by_profile: {},
      }),
    });
  });

  await page.route(/http:\/\/127\.0\.0\.1:8000\/api\/v1\/seedbox\/history.*/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ entries: [{ seedbox: "main-seedbox", action: "push", status: "ok" }] }),
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

  const uploadState = { enabled: false, auto_upload: false };
  await page.route("http://127.0.0.1:8000/api/v1/upload/state", async (route) => {
    if (route.request().method().toUpperCase() === "POST") {
      const body = route.request().postDataJSON() as { enabled: boolean; auto_upload?: boolean };
      uploadState.enabled = body.enabled;
      uploadState.auto_upload = body.auto_upload ?? uploadState.auto_upload;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(uploadState),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/history?limit=20", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        entries: [
          {
            tracker: "bhd",
            success: true,
            timestamp: new Date().toISOString(),
            message: "ok",
            errors: [],
            upload_time: 0,
          },
        ],
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/modules/run", async (route) => {
    const body = route.request().postDataJSON() as { module: string };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        argv: ["python", "-m", "swirrl", body.module],
        returncode: 0,
        stdout: `ran ${body.module}`,
        stderr: "",
        parsed_kind: null,
        parsed_payload: null,
      }),
    });
  });

  let jobSeq = 1;
  await page.route("http://127.0.0.1:8000/api/v1/modules/jobs**", async (route) => {
    if (route.request().method().toUpperCase() === "POST") {
      const id = `job-final-${jobSeq++}`;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id,
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

  await page.route("http://127.0.0.1:8000/api/v1/settings/tmdb-token", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ token: "", is_set: false, encrypted: true }),
    });
  });

  await page.route(/http:\/\/127\.0\.0\.1:8000\/api\/v1\/settings\/provider-token\/.*/, async (route) => {
    const provider = route.request().url().split("/").pop() ?? "unknown";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ provider, token: "", is_set: false, encrypted: true }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/torrent/announces", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        announces: [{ value: "https://tracker.example/announce", label: "bhd", is_selected: true }],
        selected_announce: "https://tracker.example/announce",
      }),
    });
  });

  await page.route(/http:\/\/127\.0\.0\.1:8000\/api\/v1\/upload\/image-host-key\/.*/, async (route) => {
    const host = route.request().url().split("/").pop() ?? "imgbb";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ host, key: "", is_set: false, encrypted: true }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/upload/torrent-client-password", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ is_set: false, encrypted: true }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/watch/folders", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ folders: [] }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/watch/service", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "stopped", pid: null }),
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
        watcher: { status: "running", folders_active: 1, last_error: null },
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/tools/check", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tools: [{ name: "ffmpeg", binary: "ffmpeg", ok: true, path: "C:/bin/ffmpeg.exe" }],
      }),
    });
  });

  await page.goto("/settings-setup");
  await page.getByRole("button", { name: "Save" }).first().click();
  await expect(page.getByText("C:/cfg/swirrl.yaml")).toBeVisible();

  await page.goto("/seedbox");
  await page.getByLabel("Profile name").fill("edge-seed");
  await page.getByLabel("rclone connection name").fill("edge-remote");
  await page.getByLabel("Base remote folder").fill("/edge");
  await page.getByRole("button", { name: "Add" }).click();
  const edgeTitle = page.locator("p.text-base.font-semibold", { hasText: "edge-seed" }).first();
  const edgeCard = edgeTitle.locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]");
  await expect(edgeCard).toBeVisible();
  await edgeCard.getByRole("button", { name: "Set Default" }).click();
  await edgeCard.getByRole("button", { name: "Remove" }).click();
  await expect(edgeCard).toHaveCount(0);

  await page.goto("/upload");
  await page.getByRole("button", { name: "bhd" }).click();
  await expect(page.getByText("BHD_TOKEN")).toBeVisible();
  await page.getByRole("button", { name: "Enable" }).click();
  await expect(page.getByRole("button", { name: "Disable" })).toBeVisible();

  await page.goto("/pipeline");
  await page.getByRole("button", { name: "Run Pipeline" }).click();
  await expect(page.getByText("Release Path Required.")).toBeVisible();
  await page.getByLabel("Release folder").fill("C:/Releases/Movie.Release");
  await page.getByRole("button", { name: "Run Pipeline" }).click();
  await expect(page.getByRole("link", { name: "Debug →" })).toBeVisible();

  await page.goto("/batch");
  await page.getByRole("button", { name: "Run Batch" }).click();
  await expect(page.getByText("Parent Path Required.")).toBeVisible();
  await page.getByLabel("Releases folder").fill("C:/Releases");
  await page.getByRole("button", { name: "Run Batch" }).click();
  await expect(page.getByRole("link", { name: "Debug →" })).toBeVisible();
});
