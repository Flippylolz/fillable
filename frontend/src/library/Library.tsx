import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import { formatBytes, formatDate } from "../i18n";
import { useLibrary, type Kind } from "./useLibrary";
import "./library.css";
import { DownloadSaved } from "./DownloadSaved";
import { ProcessingStatus } from "./ProcessingStatus";
import { DeleteResource } from "./DeleteResource";
import { UseTemplate } from "./UseTemplate";
import { newKey } from "./operationKey";

type SortOrder = "newest" | "oldest" | "titleAsc" | "titleDesc";

export function Library({ csrfToken, disabled, onBusy, onDirty, onSaved, onOpen, refreshRevision = 0, tab: tabProp, onTabChange }: {
  csrfToken: string; disabled: boolean; onBusy: (value: boolean) => void;
  onDirty: (value: boolean) => void; onSaved: () => void;
  onOpen?: (identity: string) => void;
  refreshRevision?: number;
  tab?: Kind; onTabChange?: (tab: Kind) => void;
}) {
  const { t, i18n } = useTranslation();
  const [internalTab, setInternalTab] = useState<Kind>("template");
  const tab = tabProp ?? internalTab;
  function setTab(next: Kind) { setInternalTab(next); onTabChange?.(next); }
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortOrder>("newest");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [kind, setKind] = useState<Kind>("template");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [revision, setRevision] = useState(0);
  const key = useRef(newKey());
  const input = useRef<HTMLInputElement>(null);
  const lifetime = useRef(new AbortController());
  const data = useLibrary(tab, revision + refreshRevision);
  const blocked = busy || disabled;

  useEffect(() => {
    lifetime.current = new AbortController();
    return () => { lifetime.current.abort(); onBusy(false); };
  }, [onBusy]);
  useEffect(() => { onDirty(file !== null); }, [file, onDirty]);

  // Search narrows the loaded cards by title or original filename; sorting
  // orders the visible gallery client-side on top of the API cursor page.
  const needle = query.trim().toLowerCase();
  const visible = needle
    ? data.items.filter(item => item.title.toLowerCase().includes(needle) || item.original_filename.toLowerCase().includes(needle))
    : data.items;
  const items = [...visible];
  if (sort === "newest") items.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  if (sort === "oldest") items.sort((a, b) => a.updated_at.localeCompare(b.updated_at));
  if (sort === "titleAsc") items.sort((a, b) => a.title.localeCompare(b.title, i18n.language));
  if (sort === "titleDesc") items.sort((a, b) => b.title.localeCompare(a.title, i18n.language));

  function changed() { key.current = newKey(); setError(""); setSaved(""); }
  function choose(next: File | null) {
    changed(); setFile(next);
    setTitle(next ? Array.from(next.name.replace(/\.docx$/i, "")).slice(0, 160).join("") : "");
  }
  // The title link stretches over the whole card; modified clicks keep the
  // native new-tab behavior and blocked sessions swallow the activation.
  function openCard(event: MouseEvent<HTMLAnchorElement>, identity: string) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (blocked || onOpen) event.preventDefault();
    if (!blocked) onOpen?.(identity);
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
        if (code === "operation_aborted" || code === "operation_conflict" || code === "rate_limited") key.current = newKey();
      }
    } catch {
      if (!controller.signal.aborted) setError("internal_error");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); onBusy(false); }
    }
  }
  const bytes = formatBytes;

  return <section className="library" aria-labelledby="library-title">
    <header className="library-topbar">
      <div className="library-titles">
        <h2 id="library-title">{t("library.title")}</h2>
        <p>{t("library.description")}</p>
      </div>
      <div className="library-tools">
        <input type="search" className="library-search" aria-label={t("library.search")}
          placeholder={t("library.search")} value={query} disabled={blocked}
          onChange={event => setQuery(event.target.value)} />
        <button type="button" className="library-refresh" disabled={blocked}
          onClick={() => setRevision(value => value + 1)}>{t("library.refresh")}</button>
        <button type="button" className="primary library-upload-toggle" disabled={blocked}
          aria-expanded={uploadOpen} aria-controls="library-upload"
          onClick={() => setUploadOpen(open => !open)}>{t("library.uploadAction")}</button>
      </div>
    </header>
    <form id="library-upload" className="library-upload" hidden={!uploadOpen} aria-labelledby="upload-title" onSubmit={event => void upload(event)}>
      <h3 id="upload-title">{t("library.uploadTitle")}</h3>
      <p>{t("library.uploadHint")}</p>
      <label>{t("library.file")}<input ref={input} type="file" accept=".docx" disabled={blocked} onChange={event => choose(event.target.files?.[0] ?? null)} /></label>
      <label>{t("library.documentTitle")}<input value={title} maxLength={160} disabled={blocked} onChange={event => { changed(); setTitle(event.target.value); }} /></label>
      <label>{t("library.kind")}<select value={kind} disabled={blocked} onChange={event => { changed(); setKind(event.target.value === "template" ? "template" : "document"); }}>
        <option value="template">{t("library.template")}</option><option value="document">{t("library.document")}</option>
      </select></label>
      <button type="submit" className="primary" disabled={blocked}>{t(busy ? "library.uploading" : "library.upload")}</button>
      {error && <p role="alert">{apiErrorMessage(error)}</p>}
      {saved && <p role="status">{t("library.uploadSaved", { title: saved })}</p>}
    </form>
    <div className="library-viewbar">
      <label className="library-sort">
        {t("library.sort")}
        <select value={sort} disabled={blocked} onChange={event => setSort(event.target.value as SortOrder)}>
          <option value="newest">{t("library.sortNewest")}</option>
          <option value="oldest">{t("library.sortOldest")}</option>
          <option value="titleAsc">{t("library.sortTitleAsc")}</option>
          <option value="titleDesc">{t("library.sortTitleDesc")}</option>
        </select>
      </label>
    </div>
    <section id="library-list" aria-label={t("library.title")} aria-busy={data.loading || data.more}>
      {data.loading && <p role="status">{t("library.loading")}</p>}
      {data.error && <p role="alert">{apiErrorMessage(data.error)}</p>}
      {!data.loading && !data.error && ((needle ? items.length === 0 : data.items.length === 0)) &&
        <p className="library-empty">{t(needle ? "library.searchEmpty" : tab === "template" ? "library.emptyTemplates" : "library.emptyDocuments")}</p>}
      <div className="library-items">{items.map(item => <article key={item.id} aria-label={item.title} className="library-item">
        <div className="library-document-cover" aria-hidden="true"><span className="library-paper"><i /><i /><i /><i /><i /></span><span className="library-format">{t("library.format")}</span></div>
        <h3>{item.deletion_pending ? item.title : <a className="library-card-open" href={`/editor/${item.id}`} aria-disabled={blocked} onClick={event => openCard(event, item.id)}>{item.title}</a>}</h3><p className="library-filename">{item.original_filename}</p>
        {item.deletion_pending ? <p role="status">{t("library.deletionPending")}</p> : <><p>{t("library.saved")}</p><ProcessingStatus key={item.current_version_id} item={item} csrfToken={csrfToken} disabled={blocked} /></>}
        <p>{t("library.updated", { date: formatDate(new Date(item.updated_at), { dateStyle: "medium", timeStyle: "short" }) })}</p><p>{bytes(item.size_bytes)}</p>
        <div className="library-actions">
          {!item.deletion_pending && item.kind === "template" && <UseTemplate key={item.current_version_id} item={item} csrfToken={csrfToken} disabled={blocked} onBusy={onBusy} onCreated={created => { setTab("document"); setRevision(value => value + 1); onSaved(); onOpen?.(created.id); }} />}
          {!item.deletion_pending && <DownloadSaved item={item} disabled={blocked} />}
          <DeleteResource item={item} csrfToken={csrfToken} disabled={blocked} onBusy={onBusy} onChanged={() => { setRevision(value => value + 1); onSaved(); }} />
        </div>
      </article>)}</div>
      {data.next && <button type="button" disabled={data.more || blocked} onClick={() => void data.loadMore()}>{t(data.more ? "library.loading" : "library.more")}</button>}
    </section>
  </section>;
}
