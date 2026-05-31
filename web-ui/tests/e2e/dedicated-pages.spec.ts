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
    const method = route.request().method().toUpperCase();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          profiles: [],
          active: null,
        }),
      });
      return;
    }
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

test("dedicated and wave pages render and run mocked commands", async ({ page }) => {
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

  await page.route("http://127.0.0.1:8000/api/v1/settings/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        settings_path: "C:/cfg/swirrl.yaml",
        config_dir: "C:/cfg",
        cache_dir: "C:/cache",
        settings: { general: { locale: "en" } },
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
        settings: { general: { locale: "en" }, seedbox: { max_concurrent_uploads: 3 } },
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
        default_by_profile: {},
      }),
    });
  });

  await page.route(/http:\/\/127\.0\.0\.1:8000\/api\/v1\/seedbox\/history.*/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        entries: [{ seedbox: "main-seedbox", action: "push", status: "ok" }],
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

  await page.route("http://127.0.0.1:8000/api/v1/upload/tracker/bhd", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        tracker: { name: "bhd", type: "unit3d", url: "https://tracker.example", token_env: "BHD_TOKEN" },
      }),
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
      body: JSON.stringify({
        provider,
        token: "",
        is_set: false,
        encrypted: true,
      }),
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

  await page.route("http://127.0.0.1:8000/api/v1/modules/spec", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        modules: [
          {
            name: "watch",
            label: "Watch",
            help: "Watch module",
            is_group: false,
            destructive: false,
            supports_dry_run: false,
            parameters: [],
            subcommands: [],
          },
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
        argv: ["python", "-m", "swirrl", body.module, ...body.args_text.split(" ").filter(Boolean)],
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
      const id = `job-studio-${jobSeq++}`;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id,
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
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByText("main-seedbox").first()).toBeVisible();
  await expect(page.getByText("bhd")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).first().click();
  await expect(page.getByText("Saved")).toBeVisible();

  await page.goto("/seedbox");
  await expect(page.getByRole("heading", { name: "Seedbox" })).toBeVisible();
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByRole("link", { name: "Debug →" })).toBeVisible();

  await page.goto("/upload");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText("ran upload")).toBeVisible();

  await page.goto("/pipeline");
  await page.getByLabel("Release folder").fill("C:/Releases/My.Release");
  await page.getByRole("button", { name: "Run Pipeline" }).click();
  await expect(page.getByRole("link", { name: "Debug →" })).toBeVisible();

  await page.goto("/batch");
  await page.getByLabel("Releases folder").fill("C:/Releases");
  await page.getByRole("button", { name: "Run Batch" }).click();
  await expect(page.getByRole("link", { name: "Debug →" })).toBeVisible();

  await page.goto("/studio/watch");
  await expect(page.getByRole("heading", { name: /Module Studio/ })).toBeVisible();
  await page.getByRole("button", { name: "Execute" }).click();
  await expect(page.getByRole("button", { name: "Open latest job" })).toBeVisible();

  await page.goto("/studios");
  await expect(page.getByRole("heading", { name: "Modules" })).toBeVisible();
  await page.getByRole("link", { name: "Open watch" }).click();
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByRole("link", { name: "Debug →" })).toBeVisible();
});
