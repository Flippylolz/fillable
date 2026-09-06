import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import type { Resource } from "./useLibrary";

export function DownloadSaved({ item, disabled }: { item: Resource; disabled: boolean }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lifetime = useRef(new AbortController());
  useEffect(() => {
    lifetime.current = new AbortController();
    return () => lifetime.current.abort();
  }, []);
  async function download() {
    if (busy || disabled) return;
    const controller = lifetime.current;
    setBusy(true); setError("");
    try {
      const result = await api.GET("/api/documents/{identity}/download", {
        params: { path: { identity: item.id } }, parseAs: "blob", signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (result.data) {
        const url = URL.createObjectURL(result.data);
        const link = document.createElement("a");
        link.href = url; link.download = item.original_filename;
        document.body.append(link);
        try { link.click(); }
        finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
      } else setError(result.error.error.code);
    } catch {
      if (!controller.signal.aborted) setError("internal_error");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return <div className="library-download">
    <button type="button" disabled={busy || disabled} onClick={() => void download()}>{t(busy ? "library.downloading" : "library.downloadSaved")}</button>
    {error && <p role="alert">{apiErrorMessage(error)}</p>}
  </div>;
}
