import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";

export function DownloadVersion({ identity, version, filename }: { identity: string; version: string; filename: string }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const lifetime = useRef(new AbortController());
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    return () => controller.abort();
  }, []);
  async function download() {
    if (busy) return;
    const { signal } = lifetime.current;
    setBusy(true); setError("");
    try {
      const result = await api.GET("/api/documents/{identity}/versions/{version}/download", {
        params: { path: { identity, version } }, parseAs: "blob", signal,
      });
      if (signal.aborted) return;
      if (!result.data) { setError(result.error.error.code); return; }
      if (result.response.headers.get("X-Fillable-Version") !== version) { setError("revision"); return; }
      const url = URL.createObjectURL(result.data), link = document.createElement("a");
      link.href = url; link.download = filename; document.body.append(link);
      try { link.click(); } finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    } catch { if (!signal.aborted) setError("internal_error"); }
    finally { if (!signal.aborted) setBusy(false); }
  }
  return <div><button type="button" disabled={busy} onClick={() => void download()}>{t(busy ? "library.downloading" : "history.download")}</button>
    {error && <p role="alert">{error === "revision" ? t("history.downloadMismatch") : error === "operation_in_progress" ? t("history.operation_in_progress") : apiErrorMessage(error)}</p>}</div>;
}
