import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { api, apiErrorMessage } from "../api";
import { DocumentEditor } from "../editor/DocumentEditor";
import { DownloadSaved } from "../library/DownloadSaved";
import "./workspace.css";

export function Workspace({ identity, dirty, onDirty }: { identity: string; dirty: boolean; onDirty: (dirty: boolean) => void }) {
  const { t } = useTranslation();
  const [saved, setSaved] = useState<components["schemas"]["ContentInfo"] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
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
      <h2 id="workspace-title">{saved ? saved.resource.title : t("workspace.title")}</h2>
      {saved && <p>{t(saved.resource.kind === "template" ? "workspace.template" : "workspace.document")}</p>}
    </div>{saved && <DownloadSaved item={saved.resource} disabled={false} />}</div>
    {error && <div role="alert"><p>{apiErrorMessage(error)}</p><button onClick={() => setAttempt(value => value + 1)}>{t("workspace.retry")}</button></div>}
    {!saved && !error && <p role="status">{t("workspace.loading")}</p>}
    {saved && <><p role="status" className="workspace-save-state">{t(dirty ? "workspace.unsaved" : "workspace.saved")}</p>
      <DocumentEditor initialDocument={saved.document} onDocumentChange={() => onDirty(true)} /></>}
  </section>;
}
