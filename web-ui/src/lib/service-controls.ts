import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "@/lib/api/client";
import { reloadService, setServiceDrain, shutdownService } from "@/lib/api/endpoints";

export type ServiceControlActionState = { kind: "success" | "error"; message: string } | null;

type RefreshFn = (() => Promise<unknown> | unknown) | undefined;

function extractApiError(err: unknown): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.body) as { detail?: string };
      return parsed.detail ?? err.message;
    } catch {
      return err.message;
    }
  }
  return err instanceof Error ? err.message : String(err);
}

async function runRefresh(fn: RefreshFn): Promise<void> {
  if (!fn) return;
  await fn();
}

export function useServiceControls(options?: {
  refreshPrimary?: RefreshFn;
  refreshSecondary?: RefreshFn;
}) {
  const [actionState, setActionState] = useState<ServiceControlActionState>(null);
  const [confirmShutdown, setConfirmShutdown] = useState(false);

  const reloadMutation = useMutation({
    mutationFn: reloadService,
    onSuccess: async () => {
      setActionState({ kind: "success", message: "Service reload requested." });
      await Promise.all([runRefresh(options?.refreshPrimary), runRefresh(options?.refreshSecondary)]);
    },
    onError: (err) => {
      setActionState({ kind: "error", message: extractApiError(err) });
    },
  });

  const drainMutation = useMutation({
    mutationFn: (enabled: boolean) => setServiceDrain(enabled),
    onSuccess: async (_result, enabled) => {
      setActionState({
        kind: "success",
        message: enabled ? "Queue drain enabled." : "Queue drain disabled.",
      });
      await runRefresh(options?.refreshPrimary);
    },
    onError: (err) => {
      setActionState({ kind: "error", message: extractApiError(err) });
    },
  });

  const shutdownMutation = useMutation({
    mutationFn: shutdownService,
    onSuccess: async (result) => {
      setActionState({
        kind: "success",
        message: result.already_requested
          ? "Shutdown was already requested."
          : "Shutdown scheduled.",
      });
      setConfirmShutdown(false);
      await runRefresh(options?.refreshPrimary);
    },
    onError: (err) => {
      setActionState({ kind: "error", message: extractApiError(err) });
    },
  });

  return {
    actionState,
    confirmShutdown,
    setConfirmShutdown,
    requestReload: () => reloadMutation.mutate(),
    requestDrain: (enabled: boolean) => drainMutation.mutate(enabled),
    requestShutdown: () => shutdownMutation.mutate(),
    isPending: reloadMutation.isPending || drainMutation.isPending || shutdownMutation.isPending,
  };
}
