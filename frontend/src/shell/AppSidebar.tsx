import { useEffect, useRef, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import { apiErrorMessage } from "../api";
import { formatBytes } from "../i18n";
import { useStorageUsage } from "./useStorageUsage";
import "./shell.css";

export type Page = "documents" | "editor" | "profile";
type Kind = "template" | "document";

/** The left rail of the gallery shell: brand, sections, storage and session.
    On narrow screens it becomes an off-canvas drawer opened by the menu bar. */
export function AppSidebar({ page, tab, opened, name, usageRevision, locked,
  drawerOpen, onClose, onLibrary, onLogout, logoutDisabled, connection, onRetry, navigate }: {
  page: Page; tab: Kind; opened: string | null; name: string; usageRevision: number;
  locked: boolean; drawerOpen: boolean; onClose: () => void;
  onLibrary: (tab: Kind) => void; onLogout: () => void; logoutDisabled: boolean;
  connection: "loading" | "ok" | "error"; onRetry: () => void;
  navigate: (event: MouseEvent<HTMLAnchorElement>, path: string) => void;
}) {
  const { t } = useTranslation();
  const { usage, error } = useStorageUsage(usageRevision);
  const firstLink = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    if (!drawerOpen) return;
    firstLink.current?.focus();
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [drawerOpen, onClose]);
  const lockedAttributes = { "aria-disabled": locked || undefined } as const;
  return <>
    <div className="shell-scrim" hidden={!drawerOpen} onClick={onClose} aria-hidden="true" />
    <aside id="app-sidebar" className={drawerOpen ? "app-sidebar app-sidebar-open" : "app-sidebar"}>
      <a ref={firstLink} className="shell-brand" href="/documents" aria-label={t("navigation.home")}
        onClick={event => { onClose(); navigate(event, "/documents"); }}>
        <span className="app-document-icon" aria-hidden="true" />
        <h1 className="shell-brand-name">{t("app.title")}</h1>
        <span className="shell-brand-sub" aria-hidden="true">{t("shell.library")}</span>
      </a>
      <nav className="shell-nav" aria-label={t("navigation.label")}>
        <a href="/documents" {...lockedAttributes} aria-current={page === "documents" && tab === "document" ? "page" : undefined}
          onClick={event => { onClose(); onLibrary("document"); navigate(event, "/documents"); }}>{t("navigation.documents")}</a>
        <a href="/documents" {...lockedAttributes} aria-current={page === "documents" && tab === "template" ? "page" : undefined}
          onClick={event => { onClose(); onLibrary("template"); navigate(event, "/documents"); }}>{t("navigation.templates")}</a>
        {opened && <a href={`/editor/${opened}`} {...lockedAttributes} aria-current={page === "editor" ? "page" : undefined}
          onClick={event => { onClose(); navigate(event, `/editor/${opened}`); }}>{t("workspace.title")}</a>}
        <a href="/profile" {...lockedAttributes} aria-current={page === "profile" ? "page" : undefined}
          onClick={event => { onClose(); navigate(event, "/profile"); }}>{t("profile.title")}</a>
      </nav>
      <section className="shell-storage" aria-label={t("profile.storage")}>
        <p className="shell-storage-title">{t("profile.storage")}</p>
        {usage ? <>
          <p>{t("library.usage", { used: formatBytes(usage.used_bytes), limit: formatBytes(usage.limit_bytes) })}</p>
          <meter aria-label={t("profile.storage")} min={0} max={Math.max(1, usage.limit_bytes)} value={Math.min(usage.used_bytes + usage.reserved_bytes, usage.limit_bytes)} />
          <p>{t("library.available", { available: formatBytes(usage.available_bytes), reserved: formatBytes(usage.reserved_bytes) })}</p>
          {usage.over_limit && <p role="status">{t("profile.overLimit")}</p>}
        </> : <p role={error ? "alert" : "status"}>{error ? apiErrorMessage(error) : t("profile.usageLoading")}</p>}
      </section>
      <footer className="shell-footer">
        <p className="shell-session">{t("auth.signedIn", { name })}</p>
        <button type="button" disabled={logoutDisabled} onClick={onLogout}>{t("auth.logout")}</button>
        <p className={`shell-connection shell-connection-${connection}`} role="status">{t(`health.${connection}`)}</p>
        {connection === "error" && <button type="button" onClick={onRetry}>{t("health.retry")}</button>}
      </footer>
    </aside>
  </>;
}
