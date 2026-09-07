import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { api, apiErrorMessage } from "../api";
import { DocumentEditor } from "../editor/DocumentEditor";
import { DownloadSaved } from "../library/DownloadSaved";
import "./workspace.css";
import { useDiscovery } from "./useDiscovery";
import { WorkspaceSettings } from "./WorkspaceSettings";

export function Workspace({ identity, dirty, onDirty, csrfToken, onBack, onChanged, onBusy }: {
  identity: string; dirty: boolean; onDirty: (dirty: boolean) => void; csrfToken: string;
  onBack?: () => void; onChanged?: () => void; onBusy?: (busy: boolean) => void;
}) {
  const { t } = useTranslation();
  const [saved, setSaved] = useState<components["schemas"]["ContentInfo"] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [zoom, setZoom] = useState(1), [highlight, setHighlight] = useState(true);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const documentDirty = useRef(dirty);
  const markDocument = useCallback(() => { documentDirty.current = true; onDirty(true); }, [onDirty]);
  const markTitle = useCallback((value: boolean) => { onDirty(documentDirty.current || value); }, [onDirty]);
  const settingsActivity = useCallback((value: boolean) => { setSettingsBusy(value); onBusy?.(value); }, [onBusy]);
  const discovery = useDiscovery(saved?.resource ?? null, csrfToken);
  function reopen() {
    if (dirty && !window.confirm(t("workspace.discard"))) return;
    documentDirty.current = false;
    setSaved(null); onDirty(false); setAttempt(value => value + 1);
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
    <div className="workspace-toolbar"><div>
      {onBack && <button type="button" disabled={settingsBusy} onClick={onBack}>{t("workspace.back")}</button>}
      <h2 id="workspace-title">{saved ? saved.resource.title : t("workspace.title")}</h2>
      {saved && <p>{t(saved.resource.kind === "template" ? "workspace.template" : "workspace.document")}</p>}
    </div>{saved && <DownloadSaved item={saved.resource} disabled={false} />}</div>
    {error && <div role="alert"><p>{apiErrorMessage(error)}</p><button onClick={() => setAttempt(value => value + 1)}>{t("workspace.retry")}</button></div>}
    {!saved && !error && <p role="status">{t("workspace.loading")}</p>}
    {saved && <><p role="status" className="workspace-save-state">{t(dirty ? "workspace.unsaved" : "workspace.saved")}</p>
      <WorkspaceSettings item={saved.resource} csrfToken={csrfToken} zoom={zoom} highlight={highlight} onZoom={setZoom} onHighlight={setHighlight}
        onDirty={markTitle} onBusy={settingsActivity} onReopen={reopen} onResource={resource => { setSaved(current => current ? { ...current, resource } : current); onChanged?.(); }} />
      <div className="workspace-discovery">
        <p role="status">{t(discovery.error ? "review.unavailable" : discovery.status === "loading" ? "review.loading" : `processing.${discovery.status}`)}</p>
        {discovery.error && <p role="alert">{apiErrorMessage(discovery.error)}</p>}
        {discovery.paused && <p>{t("review.paused")}</p>}
        {(discovery.error || discovery.paused) && <button type="button" disabled={discovery.busy} onClick={() => discovery.reload()}>{t("processing.refresh")}</button>}
        {!discovery.error && (discovery.status === "failed" || discovery.status === "not_started") && <button type="button" disabled={discovery.busy} onClick={() => discovery.reload(true)}>{t(discovery.status === "failed" ? "processing.retry" : "processing.start")}</button>}
        {discovery.status === "stale" && <button type="button" onClick={reopen}>{t("review.reopen")}</button>}
      </div>
      <DocumentEditor initialDocument={saved.document} discoverySnapshot={discovery.snapshot} sourceVersion={saved.resource.current_version_id} onReopen={reopen} onDocumentChange={markDocument} zoom={zoom} highlight={highlight} /></>}
  </section>;
}
