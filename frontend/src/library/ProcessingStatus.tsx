import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import type { Resource } from "./useLibrary";

export function ProcessingStatus({ item, csrfToken, disabled }: { item: Resource; csrfToken: string; disabled: boolean }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState(item.processing_status);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [request, setRequest] = useState<{ method: "GET" | "POST" }>({ method: "GET" });
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function run(method: "GET" | "POST") {
      setError(""); setBusy(true);
      try {
        const options = {
          params: { path: { identity: item.id } }, headers: { "X-CSRF-Token": csrfToken }, signal: controller.signal,
        };
        const result = method === "POST" ? await api.POST("/api/documents/{identity}/processing", options) : await api.GET("/api/documents/{identity}/processing", options);
        if (controller.signal.aborted) return;
        if (result.data) {
          const next = result.data.source_version_id === item.current_version_id ? result.data.status : "stale";
          setStatus(next);
          if (next === "queued" || next === "running") timer = setTimeout(() => void run("GET"), 2000);
        } else setError(result.error.error.code);
      } catch {
        if (!controller.signal.aborted) setError("internal_error");
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    }
    void run(request.method);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [item.id, item.current_version_id, csrfToken, request]);

  return <div className="library-processing">
    <p role="status">{t(`processing.${status}`)}</p>
    {error && <><p role="alert">{apiErrorMessage(error)}</p><button type="button" disabled={busy} onClick={() => setRequest({ method: "GET" })}>{t("processing.refresh")}</button></>}
    {!error && (status === "failed" || status === "not_started") && <button type="button" disabled={busy || disabled} onClick={() => setRequest({ method: "POST" })}>{t(status === "failed" ? "processing.retry" : "processing.start")}</button>}
  </div>;
}
