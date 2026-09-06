import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import { formatBytes, formatDate } from "../i18n";
import { useLibrary, type Kind } from "./useLibrary";
import "./library.css";

// getRandomValues also works on the explicitly supported HTTP origin.
function newKey() { return Array.from(crypto.getRandomValues(new Uint8Array(16)), value => value.toString(16).padStart(2, "0")).join(""); }

export function Library({ csrfToken, disabled, onBusy, onDirty, onSaved }: {
  csrfToken: string; disabled: boolean; onBusy: (value: boolean) => void;
  onDirty: (value: boolean) => void; onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Kind>("template");
  const [kind, setKind] = useState<Kind>("template");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [revision, setRevision] = useState(0);
  const key = useRef(newKey());
  const input = useRef<HTMLInputElement>(null);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const lifetime = useRef(new AbortController());
  const data = useLibrary(tab, revision);
  const blocked = busy || disabled;

  useEffect(() => {
    lifetime.current = new AbortController();
    return () => { lifetime.current.abort(); onBusy(false); };
  }, [onBusy]);
  useEffect(() => { onDirty(file !== null); }, [file, onDirty]);

  function changed() { key.current = newKey(); setError(""); setSaved(""); }
  function choose(next: File | null) {
    changed(); setFile(next);
    setTitle(next ? Array.from(next.name.replace(/\.docx$/i, "")).slice(0, 160).join("") : "");
  }
  function keyboard(event: KeyboardEvent, index: number) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? 1 : 1 - index;
    setTab(next === 0 ? "template" : "document"); tabs.current[next]?.focus();
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (blocked) return;
    setError(""); setSaved("");
    if (!file || !title.trim()) { setError("invalid_request"); return; }
    if (!/\.docx$/i.test(file.name)) { setError("unsupported_document"); return; }
    if (file.size > 10 * 1024 * 1024) { setError("file_too_large"); return; }
    const controller = lifetime.current;
    setBusy(true); onBusy(true);
    try {
      const metadata = btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify({ kind, filename: file.name, title }))));
      const result = await api.POST("/api/documents", {
        params: { header: { "X-Upload-Metadata": metadata, "idempotency-key": key.current } },
        headers: { "X-CSRF-Token": csrfToken, "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
        // OpenAPI describes binary as string; send the original File unchanged.
        body: file as unknown as string, bodySerializer: () => file, signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (result.data) {
        setSaved(result.data.title); setTab(result.data.kind);
        setFile(null); setTitle(""); key.current = newKey();
        if (input.current) input.current.value = "";
        setRevision(value => value + 1); onSaved();
      } else {
        const code = result.error.error.code;
        setError(code);
        if (code === "operation_aborted" || code === "operation_conflict") key.current = newKey();
      }
    } catch {
      if (!controller.signal.aborted) setError("internal_error");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); onBusy(false); }
    }
  }
  const bytes = formatBytes;

  return <section className="library" aria-labelledby="library-title">
    <div className="library-heading"><div><h2 id="library-title">{t("library.title")}</h2><p>{t("library.description")}</p></div>
      <button type="button" disabled={blocked} onClick={() => setRevision(value => value + 1)}>{t("library.refresh")}</button>
    </div>
    <section className="library-quota" aria-label={t("profile.storage")}>
      {data.usage ? <>
        <p>{t("library.usage", { used: bytes(data.usage.used_bytes), limit: bytes(data.usage.limit_bytes) })}</p>
        <meter aria-label={t("profile.storage")} min={0} max={Math.max(1, data.usage.limit_bytes)} value={Math.min(data.usage.used_bytes + data.usage.reserved_bytes, data.usage.limit_bytes)} />
        <p>{t("library.available", { available: bytes(data.usage.available_bytes), reserved: bytes(data.usage.reserved_bytes) })}</p>
        {data.usage.over_limit && <p role="status">{t("profile.overLimit")}</p>}
      </> : <p role={data.usageError ? "alert" : "status"}>{data.usageError ? apiErrorMessage(data.usageError) : t("profile.usageLoading")}</p>}
    </section>
    <form className="library-upload" aria-labelledby="upload-title" onSubmit={event => void upload(event)}>
      <h3 id="upload-title">{t("library.uploadTitle")}</h3>
      <p>{t("library.uploadHint")}</p>
      <label>{t("library.file")}<input ref={input} type="file" accept=".docx" disabled={blocked} onChange={event => choose(event.target.files?.[0] ?? null)} /></label>
      <label>{t("library.documentTitle")}<input value={title} maxLength={160} disabled={blocked} onChange={event => { changed(); setTitle(event.target.value); }} /></label>
      <label>{t("library.kind")}<select value={kind} disabled={blocked} onChange={event => { changed(); setKind(event.target.value === "template" ? "template" : "document"); }}>
        <option value="template">{t("library.template")}</option><option value="document">{t("library.document")}</option>
      </select></label>
      <button type="submit" disabled={blocked}>{t(busy ? "library.uploading" : "library.upload")}</button>
      {error && <p role="alert">{apiErrorMessage(error)}</p>}
      {saved && <p role="status">{t("library.uploadSaved", { title: saved })}</p>}
    </form>
    <div role="tablist" aria-label={t("library.title")} className="library-tabs">
      {(["template", "document"] as const).map((value, index) => <button key={value} ref={node => { tabs.current[index] = node; }} type="button" role="tab" id={`library-tab-${value}`} aria-controls="library-list" aria-selected={tab === value} tabIndex={tab === value ? 0 : -1} disabled={blocked} onKeyDown={event => keyboard(event, index)} onClick={() => setTab(value)}>{t(value === "template" ? "library.templates" : "library.documents")}</button>)}
    </div>
    <section id="library-list" role="tabpanel" aria-labelledby={`library-tab-${tab}`} aria-busy={data.loading || data.more}>
      {data.loading && <p role="status">{t("library.loading")}</p>}
      {data.error && <p role="alert">{apiErrorMessage(data.error)}</p>}
      {!data.loading && !data.error && data.items.length === 0 && <p className="library-empty">{t(tab === "template" ? "library.emptyTemplates" : "library.emptyDocuments")}</p>}
      <div className="library-items">{data.items.map(item => <article key={item.id} aria-label={item.title} className="library-item">
        <div className="library-document-cover" aria-hidden="true"><span className="library-paper"><i /><i /><i /><i /><i /></span></div>
        <h3>{item.title}</h3><p className="library-filename">{item.original_filename}</p>
        <p>{t("library.saved")}</p><p>{t("library.notStarted")}</p>
        <p>{t("library.updated", { date: formatDate(new Date(item.updated_at), { dateStyle: "medium", timeStyle: "short" }) })}</p><p>{bytes(item.size_bytes)}</p>
      </article>)}</div>
      {data.next && <button type="button" disabled={data.more || blocked} onClick={() => void data.loadMore()}>{t(data.more ? "library.loading" : "library.more")}</button>}
    </section>
  </section>;
}
