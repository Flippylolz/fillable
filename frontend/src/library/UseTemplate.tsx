import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import { newKey } from "./operationKey";
import type { Resource } from "./useLibrary";

export function UseTemplate({ item, csrfToken, disabled, onBusy, onCreated }: {
  item: Resource; csrfToken: string; disabled: boolean;
  onBusy: (value: boolean) => void; onCreated: (item: Resource) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(item.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const key = useRef(newKey());
  const lifetime = useRef(new AbortController());
  useEffect(() => {
    lifetime.current = new AbortController();
    return () => { lifetime.current.abort(); onBusy(false); };
  }, [onBusy]);
  async function create(event: FormEvent) {
    event.preventDefault();
    if (busy || disabled) return;
    if (!title.trim()) { setError("invalid_request"); return; }
    const controller = lifetime.current;
    setBusy(true); onBusy(true); setError("");
    let created: Resource | undefined;
    try {
      const result = await api.POST("/api/documents/{identity}/copies", {
        params: { path: { identity: item.id }, header: { "idempotency-key": key.current } },
        headers: { "X-CSRF-Token": csrfToken }, signal: controller.signal,
        body: { title, source_version_id: item.current_version_id },
      });
      if (controller.signal.aborted) return;
      if (result.data) created = result.data;
      else {
        const code = result.error.error.code; setError(code);
        if (code === "operation_aborted" || code === "operation_conflict" || code === "rate_limited" || code === "quota_exceeded") key.current = newKey();
      }
    } catch {
      if (!controller.signal.aborted) setError("internal_error");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); onBusy(false); }
    }
    if (created) { setOpen(false); key.current = newKey(); onCreated(created); }
  }
  return <div className="library-copy">
    {!open ? <button type="button" disabled={disabled} onClick={() => setOpen(true)}>{t("copy.use")}</button> :
      <form aria-label={t("copy.use")} onSubmit={event => void create(event)}>
        <p>{t("copy.description")}</p>
        <label>{t("copy.title")}<input autoFocus maxLength={160} value={title} disabled={busy || disabled} onChange={event => { setTitle(event.target.value); key.current = newKey(); setError(""); }} /></label>
        <button type="submit" className="primary" disabled={busy || disabled}>{t(busy ? "copy.creating" : "copy.create")}</button>
        <button type="button" disabled={busy || disabled} onClick={() => setOpen(false)}>{t("copy.cancel")}</button>
        {error && <p role="alert">{apiErrorMessage(error)}</p>}
      </form>}
  </div>;
}
