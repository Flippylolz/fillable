import { useEffect, useRef, useState } from "react";
import type { components } from "../../generated/api";
import { api } from "../api";

type Page = components["schemas"]["VersionList"];
export function useVersionHistory(identity: string) {
  const [page, setPage] = useState<Page | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const current = useRef<Page | null>(null), request = useRef<AbortController | null>(null);
  async function load(more = false) {
    const before = more ? current.current?.next_before : undefined;
    if (more && !before) return;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setError("");
    try {
      const result = await api.GET("/api/documents/{identity}/versions", {
        params: { path: { identity }, query: { limit: 20, before: before ?? undefined } }, signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (result.data) {
        const data = result.data;
        const items = more ? [...(current.current?.items ?? []), ...result.data.items] : result.data.items;
        const unique = items.filter((item, index) => items.findIndex(other => other.id === item.id) === index);
        const updated = { ...result.data, items: unique.map(item => ({ ...item, is_current: item.id === data.current_version_id })) };
        current.current = updated; setPage(updated);
      } else setError(result.error.error.code);
    } catch { if (!controller.signal.aborted) setError("internal_error"); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const loadRef = useRef(load); loadRef.current = load;
  useEffect(() => {
    current.current = null; setPage(null); void loadRef.current();
    return () => request.current?.abort();
  }, [identity]);
  return { page, busy, error, load };
}
