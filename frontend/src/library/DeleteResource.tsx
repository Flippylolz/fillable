import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import type { Resource } from "./useLibrary";

export function DeleteResource({ item, csrfToken, disabled, onBusy, onChanged }: {
  item: Resource; csrfToken: string; disabled: boolean;
  onBusy: (busy: boolean) => void; onChanged: () => void;
}) {
  const { t } = useTranslation();
  const dialog = useRef<HTMLDialogElement>(null);
  const lifetime = useRef(new AbortController());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    lifetime.current = new AbortController();
    return () => { lifetime.current.abort(); onBusy(false); };
  }, [onBusy]);
  async function remove() {
    if (busy || disabled) return;
    dialog.current?.close();
    const controller = lifetime.current;
    setBusy(true); onBusy(true); setError("");
    try {
      const result = await api.DELETE("/api/documents/{identity}", {
        params: { path: { identity: item.id } }, headers: { "X-CSRF-Token": csrfToken }, signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (result.data) onChanged();
      else setError(result.error.error.code);
    } catch {
      if (!controller.signal.aborted) setError("internal_error");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); onBusy(false); }
    }
  }
  return <div className="library-delete">
    <button type="button" disabled={busy || disabled} onClick={() => item.deletion_pending ? void remove() : dialog.current?.showModal()}>{t(busy ? "library.deleting" : item.deletion_pending ? "library.retryDeletion" : "library.delete")}</button>
    {error && <p role="alert">{apiErrorMessage(error)}</p>}
    <dialog ref={dialog} aria-labelledby={`delete-title-${item.id}`} aria-describedby={`delete-description-${item.id}`}>
      <h3 id={`delete-title-${item.id}`}>{t("library.deleteTitle", { title: item.title })}</h3>
      <p id={`delete-description-${item.id}`}>{t("library.deleteWarning")}</p>
      <div className="dialog-actions"><button type="button" autoFocus onClick={() => dialog.current?.close()}>{t("library.cancelDeletion")}</button>
        <button type="button" className="confirm-delete" onClick={() => void remove()}>{t("library.confirmDeletion")}</button></div>
    </dialog>
  </div>;
}
