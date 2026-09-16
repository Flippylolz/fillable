import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import type { Resource } from "./useLibrary";

export function TrashActions({ item, csrfToken, disabled, onBusy, onChanged }: {
  item?: Resource; csrfToken: string; disabled: boolean;
  onBusy: (busy: boolean) => void; onChanged: () => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const lifetime = useRef(new AbortController());
  useEffect(() => {
    lifetime.current = new AbortController();
    return () => { lifetime.current.abort(); onBusy(false); };
  }, [onBusy]);
  async function act(restore: boolean) {
    if (!restore && !window.confirm(t(item ? "trash.confirmDelete" : "trash.confirmEmpty", { title: item?.title }))) return;
    const controller = lifetime.current;
    setBusy(true); onBusy(true); setError(""); setPending(false);
    const options = { headers: { "X-CSRF-Token": csrfToken }, signal: controller.signal };
    try {
      const result = item
        ? restore ? await api.POST("/api/documents/{identity}/untrash", { ...options, params: { path: { identity: item.id } } })
          : await api.DELETE("/api/documents/{identity}", { ...options, params: { path: { identity: item.id } } })
        : await api.DELETE("/api/documents/trash", options);
      if (controller.signal.aborted) return;
      if (result.data) { setPending(result.data.status === "pending"); onChanged(); }
      else setError(result.error.error.code);
    } catch {
      if (!controller.signal.aborted) setError("internal_error");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); onBusy(false); }
    }
  }
  return <div className="trash-actions">
    {item && !item.deletion_pending && <button type="button" disabled={busy || disabled} onClick={() => void act(true)}>{t("trash.restore")}</button>}
    <button type="button" disabled={busy || disabled} onClick={() => void act(false)}>{t(item ? "trash.delete" : "trash.empty")}</button>
    {error && <p role="alert">{apiErrorMessage(error)}</p>}
    {pending && <p role="status">{t("library.deletionPending")}</p>}
  </div>;
}
