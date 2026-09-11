import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { api, apiErrorMessage } from "../api";
import { formatNumber } from "../i18n";
import { DocumentEditor, type PrintSource } from "../editor/DocumentEditor";
import type { EditorSnapshot, FieldSummary } from "../editor/adapter";
import { DownloadSaved } from "../library/DownloadSaved";
import { newKey } from "../library/operationKey";
import type { Resource } from "../library/useLibrary";
import "./workspace.css";
import { CopyPrompt } from "./CopyPrompt";
import { defaultCopyTitle } from "./copyTitle";
import { printDocumentNode } from "./printView";
import { useDiscovery } from "./useDiscovery";
import { useEditingLease } from "./useEditingLease";
import { WorkspaceSettings } from "./WorkspaceSettings";
import { useDocumentSave } from "./useDocumentSave";
import { useRestore } from "./useRestore";
import { useAutosave } from "./useAutosave";
import { HistoryPanel } from "./HistoryPanel";

export function Workspace({ identity, dirty, onDirty, csrfToken, onBack, onOpenResource, onChanged, onBusy, operationsPaused = false, authPaused = false }: {
  identity: string; dirty: boolean; onDirty: (dirty: boolean) => void; csrfToken: string;
  operationsPaused?: boolean; authPaused?: boolean;
  onBack?: () => void; onOpenResource?: (identity: string) => void; onChanged?: () => void; onBusy?: (busy: boolean) => void;
}) {
  const { t } = useTranslation();
  const [saved, setSaved] = useState<components["schemas"]["ContentInfo"] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [zoom, setZoom] = useState(1), [highlight, setHighlight] = useState(true);
  const [autosave, setAutosave] = useState(true);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false), [editorEpoch, setEditorEpoch] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [revision, setRevision] = useState(0), [titleDirty, setTitleDirty] = useState(false);
  const [valid, setValid] = useState(true), [composing, setComposing] = useState(false);
  const [copyOpen, setCopyOpen] = useState(false), [copyBusy, setCopyBusy] = useState(false);
  const [copyDefault, setCopyDefault] = useState(""), [copyError, setCopyError] = useState(""), [copyCreated, setCopyCreated] = useState<Resource | null>(null);
  const [printFallback, setPrintFallback] = useState(false);
  const reader = useRef<(() => EditorSnapshot) | null>(null);
  const fieldsReader = useRef<(() => FieldSummary[]) | null>(null);
  const printReader = useRef<(() => PrintSource | null) | null>(null);
  const registerReader = useCallback((read: (() => EditorSnapshot) | null) => { reader.current = read; }, []);
  const registerFieldsReader = useCallback((read: (() => FieldSummary[]) | null) => { fieldsReader.current = read; }, []);
  const registerPrintReader = useCallback((read: (() => PrintSource | null) | null) => { printReader.current = read; }, []);
  const savedRef = useRef(saved);
  savedRef.current = saved;
  const copyKey = useRef(newKey()), copyLifetime = useRef(new AbortController());
  useEffect(() => {
    copyLifetime.current = new AbortController();
    return () => copyLifetime.current.abort();
  }, [identity]);
  const markDocument = useCallback((snapshot: EditorSnapshot) => setRevision(snapshot.revision), []);
  const access = useEditingLease(saved?.resource ?? null, csrfToken, !authPaused);
  const discovery = useDiscovery(saved?.resource ?? null, csrfToken);
  const saving = useDocumentSave({ identity, csrfToken, read: () => reader.current?.() ?? null, credentials: access.credentials,
    onAccessLost: access.invalidate, onSaved: resource => {
      savedRef.current = savedRef.current ? { ...savedRef.current, resource } : savedRef.current;
      setSaved(current => current ? { ...current, resource } : current); onChanged?.();
    } });
  const restoring = useRestore({ identity, csrfToken, credentials: access.credentials, onAccessLost: access.invalidate,
    onRestored: content => {
      saving.reset(); setRevision(0); setTitleDirty(false); setValid(true); setComposing(false);
      setSaved(content); setHistoryOpen(false); setEditorEpoch(value => value + 1); onDirty(false); onChanged?.();
    } });
  const mutating = settingsBusy || saving.busy || restoring.busy || copyBusy;
  const unsaved = revision !== saving.acknowledged || titleDirty || saving.pending || saving.conflict || !!restoring.pending || restoring.conflict;
  const autosavePaused = operationsPaused || historyOpen || mutating || saving.pending || saving.conflict || !!saving.error
    || !!restoring.pending || restoring.conflict || !valid || composing || access.status !== "active";
  useAutosave({ enabled: autosave, revision, acknowledged: saving.acknowledged, paused: autosavePaused,
    save: () => {
      const snapshot = reader.current?.();
      if (snapshot && !snapshot.composing && snapshot.fieldValuesValid && access.credentials()) void saving.save();
    } });
  function restoreSelected(version: components["schemas"]["VersionInfo"]) {
    if (mutating || saving.pending || saving.conflict || restoring.conflict || composing) return;
    if ((dirty || unsaved) && !window.confirm(t(restoring.pending ? "history.retryConfirm" : "history.confirm", { number: formatNumber((restoring.pending ?? version).number) }))) return;
    void restoring.restore(version);
  }
  useEffect(() => { onDirty(unsaved); }, [unsaved, onDirty]);
  useEffect(() => { onBusy?.(mutating); }, [mutating, onBusy]);
  const busyCallback = useRef(onBusy); busyCallback.current = onBusy;
  useEffect(() => () => busyCallback.current?.(false), []);
  function reopen() {
    if (mutating) return;
    if ((dirty || unsaved) && !window.confirm(t(restoring.pending ? "history.discardPending" : saving.pending ? "save.discardPending" : "workspace.discard"))) return;
    saving.reset(); restoring.reset(); setHistoryOpen(false); setEditorEpoch(value => value + 1); setRevision(0); setTitleDirty(false);
    setSaved(null); onDirty(false); setAttempt(value => value + 1);
    setCopyOpen(false); setCopyCreated(null); setCopyError(""); setPrintFallback(false);
  }
  function openCopyPrompt() {
    if (!saved || mutating || saving.pending || saving.conflict || composing) return;
    setCopyCreated(null); setCopyError("");
    setCopyDefault(defaultCopyTitle(saved.resource.title, (fieldsReader.current?.() ?? []).map(field => field.value)));
    setCopyOpen(true);
  }
  async function createCopy(title: string) {
    if (copyBusy || !savedRef.current) return;
    setCopyBusy(true); setCopyError("");
    try {
      // The template draft is saved first; the copy snapshots the saved revision.
      if (await saving.save() === "failed") return;
      const version = savedRef.current.resource.current_version_id;
      if (!version) return;
      const result = await api.POST("/api/documents/{identity}/copies", {
        params: { path: { identity }, header: { "idempotency-key": copyKey.current } },
        headers: { "X-CSRF-Token": csrfToken }, signal: copyLifetime.current.signal,
        body: { title, source_version_id: version },
      });
      if (copyLifetime.current.signal.aborted) return;
      if (result.data) { setCopyCreated(result.data); setCopyOpen(false); copyKey.current = newKey(); }
      else {
        const code = result.error.error.code; setCopyError(code);
        if (["operation_aborted", "operation_conflict", "rate_limited", "quota_exceeded"].includes(code)) copyKey.current = newKey();
      }
    } catch {
      if (!copyLifetime.current.signal.aborted) setCopyError("internal_error");
    } finally { setCopyBusy(false); }
  }
  async function printDocument() {
    if (!saved || mutating || saving.pending || saving.conflict || composing) return;
    setPrintFallback(false);
    // The printed content must be the saved content: persist the draft first.
    if (revision !== saving.acknowledged && await saving.save() === "failed") return;
    const print = printReader.current?.();
    if (!print || !printDocumentNode(print.node, { rules: print.rules, scope: print.scope })) setPrintFallback(true);
  }
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    void api.GET("/api/documents/{identity}/content", { params: { path: { identity } }, signal: controller.signal })
      .then(result => {
        if (controller.signal.aborted) return;
        if (result.data) setSaved(result.data);
        else setError(result.error.error.code);
      }).catch(() => { if (!controller.signal.aborted) setError("internal_error"); });
    return () => controller.abort();
  }, [identity, attempt]);
  return <section className="workspace" aria-labelledby="workspace-title">
    <div className="workspace-toolbar"><div className="workspace-toolbar-main">
      {onBack && <button type="button" disabled={mutating} onClick={onBack}>{t("workspace.back")}</button>}
      <div className="workspace-titles">
        <h2 id="workspace-title">{saved ? saved.resource.title : t("workspace.title")}</h2>
        {saved && <p>{t(saved.resource.kind === "template" ? "workspace.template" : "workspace.document")}</p>}
      </div>
    </div>{saved && <div className="workspace-save-actions">
      <button type="button" className="primary" disabled={historyOpen || mutating || !!restoring.pending || restoring.conflict || saving.conflict || (!saving.pending && (revision === saving.acknowledged || !valid || composing || access.status !== "active"))}
        onClick={() => void saving.save()}>{t(saving.busy ? "save.saving" : saving.pending ? "save.retry" : "save.action")}</button>
      {saved.resource.kind === "template" && !historyOpen && <button type="button" disabled={mutating || saving.pending || saving.conflict || !!restoring.pending || restoring.conflict || composing}
        onClick={openCopyPrompt}>{t("workspace.saveToDocuments")}</button>}
      {!historyOpen && <DownloadSaved item={saved.resource} disabled={false} />}
      {!historyOpen && <button type="button" disabled={mutating || saving.pending || saving.conflict || !!restoring.pending || restoring.conflict || composing}
        onClick={() => void printDocument()}>{t("workspace.print")}</button>}
      <button type="button" disabled={mutating || composing} aria-expanded={historyOpen} onClick={() => { setHistoryOpen(value => !value); setCopyOpen(false); }}>{t(historyOpen ? "history.close" : "history.open")}</button></div>}</div>
    {copyOpen && !historyOpen && saved?.resource.kind === "template" && <CopyPrompt initialTitle={copyDefault} busy={copyBusy} error={copyError}
      disabled={saving.conflict || !!restoring.pending || restoring.conflict} onSubmit={title => void createCopy(title)} onCancel={() => setCopyOpen(false)} />}
    {printFallback && !historyOpen && <div className="workspace-print-fallback" role="alert">
      <p>{t("workspace.printUnavailable")}</p>
      {saved && <DownloadSaved item={saved.resource} disabled={mutating} />}
    </div>}
    {copyCreated && <div className="workspace-copy-created" role="status">
      <p>{t("workspace.copyCreated", { title: copyCreated.title })}</p>
      {onOpenResource && <button type="button" onClick={() => onOpenResource(copyCreated.id)}>{t("workspace.copyOpen")}</button>}
    </div>}
    {error && <div role="alert"><p>{apiErrorMessage(error)}</p><button onClick={() => setAttempt(value => value + 1)}>{t("workspace.retry")}</button></div>}
    {!saved && !error && <p role="status">{t("workspace.loading")}</p>}
    {saved && <><div className="workspace-access">
      <p role="status">{t(`lease.${access.status}`)}</p>
      {access.error && <p role="alert">{["lease_busy", "lease_lost", "revision"].includes(access.error) ? t(`lease.${access.error}`) : apiErrorMessage(access.error)}</p>}
      {access.status === "paused" && (access.error === "revision"
        ? <button type="button" onClick={reopen}>{t("review.reopen")}</button>
        : <button type="button" onClick={access.retry}>{t("lease.retry")}</button>)}
    </div><p role="status" className="workspace-save-state">{t(saving.busy ? "save.saving" : unsaved ? "workspace.unsaved" : saving.acknowledged ? "save.saved" : "workspace.saved")}</p>
      <p className="workspace-autosave-state">{t(!autosave ? "autosave.off" : saving.busy ? "save.saving" : autosavePaused ? "autosave.paused" : "autosave.on")}</p>
      {saving.error && <div className="workspace-save-error" role="alert">
        <p>{["revision", "lease_lost", "composing", "invalid_fields", "file_too_large", "upload_timeout", "upload_busy", "operation_in_progress", "operation_aborted", "invalid_document"].includes(saving.error)
          ? t(`save.${saving.error}`) : apiErrorMessage(saving.error)}</p>
        {saving.pending && <p>{t("save.uncertain")}</p>}
        {(saving.pending || saving.conflict) && <button type="button" disabled={mutating} onClick={reopen}>{t("review.reopen")}</button>}
      </div>}
      {restoring.error && <div className="workspace-save-error" role="alert">
        <p>{["revision", "lease_lost"].includes(restoring.error) ? t(`save.${restoring.error}`)
          : restoring.error === "restore_load" ? t("history.loadFailed")
          : ["operation_in_progress", "operation_aborted", "upload_busy", "file_too_large"].includes(restoring.error) ? t(`history.${restoring.error}`) : apiErrorMessage(restoring.error)}</p>
        {restoring.pending && <><p>{t("history.uncertain")}</p><button type="button" disabled={mutating || saving.pending || saving.conflict} onClick={() => restoreSelected(restoring.pending!)}>{t("history.retryRestore", { number: formatNumber(restoring.pending.number) })}</button></>}
        {(restoring.pending || restoring.conflict) && <button type="button" disabled={mutating} onClick={reopen}>{t("review.reopen")}</button>}
      </div>}
      {restoring.busy && <p role="status">{t("history.restoring")}</p>}
      {historyOpen && <HistoryPanel identity={identity} current={saved.resource.current_version_id} filename={saved.resource.original_filename}
        dirty={dirty || unsaved} blocked={saving.pending || saving.conflict || !!restoring.pending || restoring.conflict || access.status !== "active"}
        busy={mutating} onRestore={restoreSelected} onReopen={reopen} />}
      <div style={{ display: historyOpen ? "none" : undefined }}>
      <WorkspaceSettings key={editorEpoch} open={settingsOpen} onOpenChange={setSettingsOpen} item={saved.resource} csrfToken={csrfToken} zoom={zoom} highlight={highlight} onZoom={setZoom} onHighlight={setHighlight} autosave={autosave} onAutosave={setAutosave}
        disabled={saving.pending || mutating || saving.conflict || !!restoring.pending || restoring.conflict} onDirty={setTitleDirty} onBusy={setSettingsBusy} onReopen={reopen}
        onResource={resource => { setSaved(current => current ? { ...current, resource } : current); onChanged?.(); }} />
      <div className="workspace-discovery">
        <p role="status">{t(discovery.error ? "review.unavailable" : discovery.status === "loading" ? "review.loading" : `processing.${discovery.status}`)}</p>
        {discovery.error && <p role="alert">{apiErrorMessage(discovery.error)}</p>}
        {discovery.paused && <p>{t("review.paused")}</p>}
        {(discovery.error || discovery.paused) && <button type="button" disabled={discovery.busy} onClick={() => discovery.reload()}>{t("processing.refresh")}</button>}
        {!discovery.error && (discovery.status === "failed" || discovery.status === "not_started") && <button type="button" disabled={discovery.busy} onClick={() => discovery.reload(true)}>{t(discovery.status === "failed" ? "processing.retry" : "processing.start")}</button>}
        {discovery.status === "stale" && <button type="button" onClick={reopen}>{t("review.reopen")}</button>}
      </div>
      <DocumentEditor key={editorEpoch} initialDocument={saved.document} sourcePresentation={saved.presentation} discoverySnapshot={discovery.snapshot} sourceVersion={saved.resource.current_version_id} onReopen={reopen}
          onSnapshot={markDocument} onReader={registerReader} onFieldsReader={registerFieldsReader} onPrintReader={registerPrintReader} reviewSaved={saving.reviewSaved} onFieldValidityChange={setValid} onCompositionChange={setComposing}
        canEdit={access.canEdit} readOnly={access.status !== "active" || restoring.busy} zoom={zoom} highlight={highlight} /></div></>}
  </section>;
}
