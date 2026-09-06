import { useEffect, useRef, useState } from "react";
import type { components } from "../../generated/api";
import { api } from "../api";

export type Kind = "template" | "document";
export type Resource = components["schemas"]["ResourceInfo"];
type Usage = components["schemas"]["QuotaUsage"];

export function useLibrary(kind: Kind, revision: number) {
  const [items, setItems] = useState<Resource[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(false);
  const [error, setError] = useState("");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [usageError, setUsageError] = useState("");
  const lifetime = useRef(new AbortController());

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    setItems([]); setNext(null); setLoading(true); setMore(false); setError("");
    setUsage(null); setUsageError("");
    void api.GET("/api/documents", { params: { query: { kind } }, signal: controller.signal })
      .then(result => {
        if (controller.signal.aborted) return;
        if (result.data) { setItems(result.data.items); setNext(result.data.next_cursor ?? null); }
        else setError(result.error.error.code);
      })
      .catch(() => { if (!controller.signal.aborted) setError("internal_error"); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    void api.GET("/api/storage/usage", { signal: controller.signal })
      .then(result => {
        if (controller.signal.aborted) return;
        if (result.data) setUsage(result.data);
        else setUsageError(result.error.error.code);
      })
      .catch(() => { if (!controller.signal.aborted) setUsageError("internal_error"); });
    return () => controller.abort();
  }, [kind, revision]);

  async function loadMore() {
    if (!next || more || loading) return;
    const controller = lifetime.current;
    setMore(true); setError("");
    try {
      const result = await api.GET("/api/documents", { params: { query: { kind, cursor: next } }, signal: controller.signal });
      if (controller.signal.aborted) return;
      if (result.data) {
        const data = result.data;
        setItems(previous => [...new Map([...previous, ...data.items].map(item => [item.id, item])).values()]);
        setNext(data.next_cursor ?? null);
      } else setError(result.error.error.code);
    } catch {
      if (!controller.signal.aborted) setError("internal_error");
    } finally {
      if (!controller.signal.aborted) setMore(false);
    }
  }
  return { items, next, loading, more, error, usage, usageError, loadMore };
}
