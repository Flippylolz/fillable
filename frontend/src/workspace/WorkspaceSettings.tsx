import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import type { Resource } from "../library/useLibrary";

export function WorkspaceSettings({ item, csrfToken, zoom, highlight, onZoom, onHighlight, autosave, onAutosave, onResource, onDirty, onBusy, onReopen, disabled = false, open, onOpenChange }: {
  autosave?: boolean; onAutosave?: (enabled: boolean) => void;
  item: Resource; csrfToken: string; zoom: number; highlight: boolean;
  onZoom: (zoom: number) => void; onHighlight: (highlight: boolean) => void;
  onResource: (resource: Resource) => void; onDirty: (dirty: boolean) => void;
  onBusy?: (busy: boolean) => void; onReopen: () => void;
  disabled?: boolean; open: boolean; onOpenChange: (open: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const [title, setTitle] = useState(item.title);
  const [previous, setPrevious] = useState(item.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const errorId = useId();
  const lifetime = useRef(new AbortController());
  const busyChange = useRef(onBusy); busyChange.current = onBusy;
  useEffect(() => { onDirty(title.trim() !== item.title); }, [title, item.title, onDirty]);
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    return () => { controller.abort(); busyChange.current?.(false); };
  }, []);
  async function submit(action: "rename" | "reload") {
    if (busy || disabled) return;
    setError(""); setStatus("");
    const clean = title.trim();
    if (action === "rename" && (!clean || [...clean].length > 160 || [...clean].some(char => char.codePointAt(0)! < 32 || (char.codePointAt(0)! >= 0xd800 && char.codePointAt(0)! <= 0xdfff)))) {
      setError("invalid_title"); return;
    }
    const { signal } = lifetime.current;
    setBusy(true); busyChange.current?.(true);
    try {
      const result = await (action === "rename"
        ? api.PATCH("/api/documents/{identity}/title", { params: { path: { identity: item.id } }, headers: { "X-CSRF-Token": csrfToken },
          body: { title: clean, previous_title: previous, source_version_id: item.current_version_id }, signal })
        : api.GET("/api/documents/{identity}", { params: { path: { identity: item.id } }, signal }));
      if (signal.aborted) return;
      if (result.data) {
        if (result.data.current_version_id !== item.current_version_id) { setError("revision_conflict"); return; }
        setPrevious(result.data.title);
        if (action === "rename") setTitle(result.data.title);
        onResource(result.data); setStatus(action === "rename" ? "renamed" : "titleReloaded");
      } else {
        const failure = result.error.error;
        setError(failure.code === "operation_conflict" ? failure.parameters?.reason === "title" ? "title_conflict" : "revision_conflict" : failure.code);
      }
    } catch { if (!signal.aborted) setError("internal_error"); }
    finally { if (!signal.aborted) { setBusy(false); busyChange.current?.(false); } }
  }
  function rename(event: FormEvent) { event.preventDefault(); void submit("rename"); }
  // The workspace owns the open state so background refreshes cannot collapse the panel.
  return <details className="workspace-settings" open={open} onToggle={event => {
    const next = (event.target as HTMLDetailsElement).open;
    if (next !== open) onOpenChange(next);
  }}><summary>{t("workspace.settings")}</summary>
    <div className="workspace-settings-body">
      <form onSubmit={rename}>
        <label>{t("workspace.name")}<input value={title} aria-invalid={error === "invalid_title" || undefined} aria-describedby={error ? errorId : undefined}
          onChange={event => { setTitle(event.target.value); setError(""); setStatus(""); }} disabled={busy} /></label>
        <p>{t("workspace.currentTitle", { title: item.title })}</p>
        <button type="submit" disabled={busy || disabled}>{t(busy ? "workspace.working" : "workspace.rename")}</button>
        {error && <p role="alert" id={errorId}>{error === "invalid_title" ? t("workspace.renameInvalid", { limit: new Intl.NumberFormat(i18n.resolvedLanguage).format(160) })
          : error === "title_conflict" ? t("workspace.renameConflict") : error === "revision_conflict" ? t("workspace.renameStale") : apiErrorMessage(error)}</p>}
        {error === "title_conflict" && <button type="button" disabled={busy || disabled} onClick={() => void submit("reload")}>{t("workspace.reloadTitle")}</button>}
        {error === "revision_conflict" && <button type="button" disabled={busy || disabled} onClick={onReopen}>{t("review.reopen")}</button>}
        {status && <p role="status">{t(`workspace.${status}`)}</p>}
      </form>
      {onAutosave && <div className="workspace-autosave-option"><label className="workspace-highlight"><input type="checkbox" checked={autosave} onChange={event => onAutosave(event.target.checked)} />{t("autosave.enable")}</label><p>{t("autosave.storage")}</p></div>}
      <div className="workspace-view-settings">
        <label>{t("workspace.zoom")}<select value={zoom} onChange={event => onZoom(Number(event.target.value))}>
          {[0.5, 0.75, 1, 1.25, 1.5, 2].map(value => <option key={value} value={value}>{new Intl.NumberFormat(i18n.resolvedLanguage, { style: "percent", maximumFractionDigits: 0 }).format(value)}</option>)}
        </select></label>
        <label className="workspace-highlight"><input type="checkbox" checked={highlight} onChange={event => onHighlight(event.target.checked)} />{t("workspace.highlight")}</label>
      </div>
    </div>
  </details>;
}
