import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { api, apiErrorMessage } from "../api";
import { formatBytes, formatDate, formatNumber } from "../i18n";
import { DownloadVersion } from "./DownloadVersion";
import { HistoricalPreview } from "./HistoricalPreview";
import { useVersionHistory } from "./useVersionHistory";

type Version = components["schemas"]["VersionInfo"];
export function HistoryPanel({ identity, current, filename, dirty, blocked, busy, onRestore, onReopen }: {
  identity: string; current: string; filename: string; dirty: boolean; blocked: boolean; busy: boolean;
  onRestore: (version: Version) => void; onReopen: () => void;
}) {
  const { t } = useTranslation();
  const history = useVersionHistory(identity);
  const [selected, setSelected] = useState(current), [attempt, setAttempt] = useState(0);
  const [preview, setPreview] = useState<components["schemas"]["VersionContent"] | null>(null);
  const [error, setError] = useState("");
  const stale = !!history.page && history.page.current_version_id !== current;
  useEffect(() => {
    const controller = new AbortController();
    setPreview(null); setError("");
    void api.GET("/api/documents/{identity}/versions/{version}/content", {
      params: { path: { identity, version: selected } }, signal: controller.signal,
    }).then(result => {
      if (controller.signal.aborted) return;
      if (result.data && result.data.version.id === selected) setPreview(result.data);
      else setError(result.data ? "operation_conflict" : result.error.error.code);
    }).catch(() => { if (!controller.signal.aborted) setError("internal_error"); });
    return () => controller.abort();
  }, [identity, selected, attempt]);
  const versionName = (number: number) => t("history.version", { number: formatNumber(number) });
  return <section className="workspace-history" aria-label={t("history.title")}>
    <h3>{t("history.title")}</h3>
    <p role="status">{t(dirty ? "history.draftKept" : "history.readOnly")}</p>
    {history.page && <p className="history-policy">{history.page.retention.keep_latest === null
      ? t("history.retained") : t("history.keepLatest", { count: history.page.retention.keep_latest, number: formatNumber(history.page.retention.keep_latest) })}</p>}
    {stale && <div role="alert"><p>{t("history.stale")}</p><button type="button" disabled={busy} onClick={onReopen}>{t("review.reopen")}</button></div>}
    <div className="history-layout"><aside className="history-list" aria-label={t("history.versions")}>
      <button type="button" disabled={history.busy || busy} onClick={() => void history.load()}>{t("history.refresh")}</button>
      {history.error && <p role="alert">{apiErrorMessage(history.error)}</p>}
      {history.busy && <p role="status">{t("history.loading")}</p>}
      {history.page?.items.length === 0 && <p>{t("history.empty")}</p>}
      <ol>{history.page?.items.map(item => <li key={item.id}>
        <button type="button" disabled={busy} aria-current={item.id === selected ? "true" : undefined} onClick={() => setSelected(item.id)}>
          <strong>{versionName(item.number)}</strong>
          <time dateTime={item.created_at}>{formatDate(new Date(item.created_at), { dateStyle: "medium", timeStyle: "short" })}</time>
          <span>{formatBytes(item.size_bytes)}</span>
          {item.is_current && <span>{t("history.current")}</span>}
          {item.restored_from_number !== null && <span>{t("history.restoredFrom", { number: formatNumber(item.restored_from_number) })}</span>}
        </button>
      </li>)}</ol>
      {history.page?.next_before && <button type="button" disabled={history.busy || busy} onClick={() => void history.load(true)}>{t("history.more")}</button>}
    </aside><div className="history-content">
      {error && <div role="alert"><p>{["operation_in_progress", "operation_conflict"].includes(error) ? t(`history.${error}`) : apiErrorMessage(error)}</p><button type="button" disabled={busy} onClick={() => setAttempt(value => value + 1)}>{t("history.retryPreview")}</button></div>}
      {!preview && !error && <p role="status">{t("history.loadingPreview")}</p>}
      {preview && <><div className="history-actions"><h4>{versionName(preview.version.number)}</h4>
        <DownloadVersion key={selected} identity={identity} version={selected} filename={filename} />
        <button type="button" disabled={busy || blocked || stale} onClick={() => onRestore(preview.version)}>{t("history.restore")}</button>
      </div>{blocked && <p>{t("history.resolveSave")}</p>}
        <HistoricalPreview key={selected} document={preview.document} presentation={preview.presentation} /></>}
    </div></div>
  </section>;
}
