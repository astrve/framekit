import { z } from "zod";

const DEFAULT_TIMEOUT_MS = 10_000;
const TOKEN_KEY = "framekit_token";

export class ApiError extends Error {
  public readonly status: number;
  public readonly body: string;

  public constructor(message: string, status: number, body: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_FRAMEKIT_API_BASE_URL;
  if (typeof configured === "string" && configured.trim().length > 0) {
    return configured.trimEnd().replace(/\/+$/, "");
  }
  return "http://127.0.0.1:8000";
}

export async function fetchValidated<TSchema extends z.ZodTypeAny>(
  path: string,
  schema: TSchema,
  init?: RequestInit,
): Promise<z.infer<TSchema>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

  const storedToken = localStorage.getItem(TOKEN_KEY);
  const baseHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(storedToken ? { Authorization: `Bearer ${storedToken}` } : {}),
  };

  try {
    const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { ...baseHeaders, ...init?.headers },
    });

    if (!response.ok) {
      const body = await response.text();
      if (response.status === 401 && !path.startsWith("/api/v1/auth/")) {
        localStorage.removeItem(TOKEN_KEY);
        window.location.href = "/login";
      }
      throw new ApiError(`API request failed for ${path}`, response.status, body);
    }

    const json = await response.json();
    return schema.parse(json);
  } finally {
    clearTimeout(timeout);
  }
}

