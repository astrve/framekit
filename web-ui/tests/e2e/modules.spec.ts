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
  attempts?: number;
  max_attempts?: number;
  retryable?: boolean;
};

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

test("jobs flow supports create, cancel, rerun, and detail drilldown", async ({ page }) => {
  await mockShell(page);

  const now = () => new Date().toISOString();
  let sequence = 1;
  const jobs = new Map<string, JobRecord>();

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
        attempts: 1,
        max_attempts: 3,
        retryable: true,
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
          argv: ["python", "-m", "ouro", "watch", "list"],
          returncode: 0,
          stdout: '{"status":"rerun-ok"}',
          stderr: "",
          parsed_kind: "json",
          parsed_payload: { status: "rerun-ok" },
        },
        error: null,
        attempts: 2,
        max_attempts: 3,
        retryable: true,
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

  await page.goto("/studio/watch");
  await expect(page.getByRole("heading", { name: "Module Studio: watch" })).toBeVisible();

  await page.getByRole("button", { name: "Execute" }).click();
  await expect(page.getByRole("button", { name: "Open latest job" })).toBeVisible();

  await page.getByRole("button", { name: "Open latest job" }).click();
  await expect(page.getByRole("heading", { name: "Job Detail" })).toBeVisible();
  await expect(page.getByText("step 1: start")).toBeVisible();

  await page.getByRole("button", { name: "Pause follow" }).click();
  await page.getByLabel("Filter").fill("step 2");
  await expect(page.getByText("step 2: working")).toBeVisible();
  await page.getByRole("link", { name: "Back to Jobs" }).click();

  await page.getByRole("button", { name: "job-1" }).click();
  await page.getByRole("button", { name: "Cancel job" }).click();
  await expect(page.getByText("Cancelled by user.")).toBeVisible();

  await page.getByRole("button", { name: "Rerun" }).click();
  await expect(page.getByRole("button", { name: "job-2" })).toBeVisible();
  await expect(page.getByText('{"status":"rerun-ok"}')).toBeVisible();

  await page.getByRole("button", { name: "View Details" }).click();
  await expect(page.getByRole("heading", { name: "Job Detail" })).toBeVisible();
  await expect(page.getByText("job-2")).toBeVisible();
  await expect(page.getByText("Return code: 0")).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to Jobs" })).toBeVisible();
});
