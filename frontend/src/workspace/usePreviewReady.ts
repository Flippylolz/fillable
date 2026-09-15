import { useEffect, useRef } from "react";
import { api } from "../api";

/** A render receipt contains only the owned saved revision ID, never client HTML. */
export function usePreviewReady(identity: string, version: string | undefined, csrfToken: string, rendered: boolean, onReady?: () => void) {
  const notify = useRef(onReady); notify.current = onReady;
  useEffect(() => {
    if (!rendered || !version) return;
    const controller = new AbortController();
    void api.POST("/api/documents/{identity}/preview", {
      params: { path: { identity } }, headers: { "X-CSRF-Token": csrfToken },
      body: { source_version_id: version }, signal: controller.signal,
    }).then(result => { if (!controller.signal.aborted && result.data) notify.current?.(); }).catch(() => {});
    return () => controller.abort();
  }, [identity, version, csrfToken, rendered]);
}
