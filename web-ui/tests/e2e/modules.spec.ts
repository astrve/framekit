import { expect, test } from "@playwright/test";

type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

type JobRecord = {
  id: string;
  status: JobStatus;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  request: Record<string, unknown>;
  result?: {
    ok: boolean;
    argv: string[];
    returncode: number;
    stdout: string;
    stderr: string;
    parsed_kind?: string | null;
    parsed_payload?: unknown;
  } | null;
  error?: string | null;
  live_stdout?: string;
  live_stderr?: string;
};

test("modules async flow supports create cancel rerun", async ({ page }) => {
  const now = () => new Date().toISOString();
  let sequence = 1;
  const jobs = new Map<string, JobRecord>();

  await page.route("http://127.0.0.1:8000/api/v1/modules/catalog", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        modules: [
          {
            name: "inspect",
            description: "Inspect release folder.",
            destructive: false,
            supports_dry_run: false,
          },
        ],
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/modules/presets", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        presets: [
          {
            id: "inspect-release",
            label: "Inspect release",
            module: "inspect",
            args_text: '"C:/Releases/My.Release"',
            dry_run: false,
            auto_yes: false,
            confirm_destructive: false,
          },
        ],
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/v1/modules/jobs**", async (route) => {
    const req = route.request();
    const method = req.method().toUpperCase();
    const url = new URL(req.url());
    const pathname = url.pathname;

    if (pathname === "/api/v1/modules/jobs" && method === "GET") {
      const payload = { jobs: Array.from(jobs.values()).sort((a, b) => b.id.localeCompare(a.id)) };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(payload),
      });
      return;
    }

    if (pathname === "/api/v1/modules/jobs" && method === "POST") {
      const body = req.postDataJSON() as Record<string, unknown>;
      const id = `job-${sequence++}`;
      const created: JobRecord = {
        id,
        status: "running",
        created_at: now(),
        started_at: now(),
        request: body,
        result: null,
        error: null,
        live_stdout: "step 1: start\nstep 2: working",
        live_stderr: "warn: sample",
      };
      jobs.set(id, created);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(created),
      });
      return;
    }

    const rerunMatch = pathname.match(/^\/api\/v1\/modules\/jobs\/([^/]+)\/rerun$/);
    if (rerunMatch && method === "POST") {
      const source = jobs.get(rerunMatch[1]);
      if (!source) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "job not found" }),
        });
        return;
      }
      const id = `job-${sequence++}`;
      const rerun: JobRecord = {
        id,
        status: "completed",
        created_at: now(),
        started_at: now(),
        finished_at: now(),
        request: source.request,
        result: {
          ok: true,
          argv: ["python", "-m", "framekit", "inspect"],
          returncode: 0,
          stdout: '{"status":"rerun-ok"}',
          stderr: "",
          parsed_kind: "json",
          parsed_payload: { status: "rerun-ok" },
        },
        error: null,
      };
      jobs.set(id, rerun);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(rerun),
      });
      return;
    }

    const jobMatch = pathname.match(/^\/api\/v1\/modules\/jobs\/([^/]+)$/);
    if (jobMatch && method === "GET") {
      const job = jobs.get(jobMatch[1]);
      if (!job) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "job not found" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(job),
      });
      return;
    }

    if (jobMatch && method === "DELETE") {
      const existing = jobs.get(jobMatch[1]);
      if (!existing) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "job not found" }),
        });
        return;
      }
      const cancelled: JobRecord = {
        ...existing,
        status: "cancelled",
        finished_at: now(),
        error: "Cancelled by user.",
      };
      jobs.set(existing.id, cancelled);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(cancelled),
      });
      return;
    }

    await route.fulfill({
      status: 405,
      contentType: "application/json",
      body: JSON.stringify({ detail: "unsupported method" }),
    });
  });

  await page.goto("/modules");
  await expect(page.getByText("Modules Workbench")).toBeVisible();

  await page.getByRole("button", { name: "Exécuter" }).click();
  await expect(page.getByRole("button", { name: /job-1/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel job" })).toBeVisible();
  await page.getByRole("button", { name: "Ouvrir détail" }).click();
  await expect(page.getByText("step 1: start")).toBeVisible();
  await page.getByRole("button", { name: "Pause follow" }).click();
  await page.getByLabel("Filtre").fill("step 2");
  await expect(page.getByText("step 2: working")).toBeVisible();
  await page.getByRole("link", { name: "Retour modules" }).click();
  await page.getByRole("button", { name: /job-1/ }).click();

  await page.getByRole("button", { name: "Cancel job" }).click();
  await expect(page.getByText("Cancelled by user.")).toBeVisible();

  await page.getByRole("button", { name: "Rerun" }).click();
  await expect(page.getByRole("button", { name: /job-2/ })).toBeVisible();
  await expect(page.getByText("Return code: 0")).toBeVisible();
  await expect(page.getByText('{"status":"rerun-ok"}')).toBeVisible();

  await page.getByRole("button", { name: "Ouvrir détail" }).click();
  await expect(page.getByRole("heading", { name: "Job detail" })).toBeVisible();
  await expect(page.getByText("job-2")).toBeVisible();
  await expect(page.getByText("Return code: 0")).toBeVisible();
  await expect(page.getByRole("link", { name: "Retour modules" })).toBeVisible();
});
