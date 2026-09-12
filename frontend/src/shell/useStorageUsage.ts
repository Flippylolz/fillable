import { useEffect, useState } from "react";
import type { components } from "../../generated/api";
import { api } from "../api";

type Usage = components["schemas"]["QuotaUsage"];

/** Sidebar storage meter data; `revision` re-reads after saves and deletions. */
export function useStorageUsage(revision: number) {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setUsage(null); setError("");
    void api.GET("/api/storage/usage", { signal: controller.signal })
      .then(result => {
        if (controller.signal.aborted) return;
        if (result.data) setUsage(result.data);
        else setError(result.error.error.code);
      })
      .catch(() => { if (!controller.signal.aborted) setError("internal_error"); });
    return () => controller.abort();
  }, [revision]);
  return { usage, error };
}
