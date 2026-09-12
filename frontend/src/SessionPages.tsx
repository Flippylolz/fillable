import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Session } from "./accounts/Authentication";
import { Profile } from "./accounts/Profile";
import { Library } from "./library/Library";
import { Workspace } from "./workspace/Workspace";
import { AppSidebar, type Page } from "./shell/AppSidebar";
import type { Kind } from "./library/useLibrary";

function route(path: string): { page: Page; identity: string | null } {
  const match = /^\/editor\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(path);
  return { page: match ? "editor" : path === "/profile" ? "profile" : "documents", identity: match?.[1] ?? null };
}
export function SessionPages({ session, accept, authBusy, setAuthBusy, setLeaveGuard, authPaused = false, logout, connection, onRetry }: {
  authPaused?: boolean;
  session: Session; accept: (session: Session) => void; authBusy: boolean;
  setAuthBusy: (busy: boolean) => void; setLeaveGuard?: (guard: () => boolean) => void;
  logout: () => void; connection: "loading" | "ok" | "error"; onRetry: () => void;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState<Page>(() => route(window.location.pathname).page);
  const [opened, setOpened] = useState(() => route(window.location.pathname).identity);
  const [busy, setBusy] = useState(false);
  const [fileDirty, setFileDirty] = useState(false);
  const [editorDirty, setEditorDirty] = useState(false);
  const [usageRevision, setUsageRevision] = useState(0);
  const [libraryTab, setLibraryTab] = useState<Kind>("template");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const lastPath = useRef(window.location.pathname);
  const updateBusy = useCallback((value: boolean) => { setBusy(value); setAuthBusy(value); }, [setAuthBusy]);
  const saved = useCallback(() => setUsageRevision(value => value + 1), []);
  const go = useCallback((path: string, fromHistory = false) => {
    const next = route(path);
    if (busy || authBusy || authPaused || (next.identity && next.identity !== opened && editorDirty && !window.confirm(t("workspace.discard")))) {
      if (fromHistory) window.history.replaceState(null, "", lastPath.current);
      return;
    }
    if (next.identity && next.identity !== opened) { setOpened(next.identity); setEditorDirty(false); }
    const canonical = next.identity ? `/editor/${next.identity}` : `/${next.page}`;
    if (!fromHistory) window.history.pushState(null, "", canonical);
    else if (path !== canonical) window.history.replaceState(null, "", canonical);
    lastPath.current = canonical; setPage(next.page);
  }, [busy, authBusy, opened, editorDirty, t, authPaused]);
  useEffect(() => {
    const initial = route(window.location.pathname);
    const canonical = initial.identity ? `/editor/${initial.identity}` : `/${initial.page}`;
    window.history.replaceState(null, "", canonical); lastPath.current = canonical;
  }, []);
  useEffect(() => {
    const pop = () => go(window.location.pathname, true);
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, [go]);
  useEffect(() => {
    setLeaveGuard?.(() => !(fileDirty || editorDirty) || window.confirm(t("workspace.discard")));
    return () => setLeaveGuard?.(() => true);
  }, [fileDirty, editorDirty, setLeaveGuard, t]);
  useEffect(() => {
    if (!busy && !fileDirty && !editorDirty) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [busy, fileDirty, editorDirty]);
  function navigate(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); go(path);
  }
  // Sidebar sections aim at the same library page with a preselected tab.
  function goLibrary(tab: Kind) { setLibraryTab(tab); go("/documents"); }
  if (!session.user) return null;
  const locked = busy || authBusy || authPaused;
  return <div className="app-shell">
    <header className="shell-mobilebar">
      <button type="button" className="shell-menu" aria-expanded={drawerOpen} aria-controls="app-sidebar"
        aria-label={t("shell.menu")} disabled={locked} onClick={() => setDrawerOpen(true)}>
        <i /><i /><i />
      </button>
      <a className="shell-brand-compact" href="/documents" onClick={event => navigate(event, "/documents")}>
        <span className="app-document-icon" aria-hidden="true" />{t("app.title")}
      </a>
    </header>
    <AppSidebar page={page} tab={libraryTab} opened={opened} name={session.user.display_name}
      usageRevision={usageRevision} locked={locked} drawerOpen={drawerOpen} onClose={() => setDrawerOpen(false)}
      onLibrary={goLibrary} onLogout={logout} logoutDisabled={locked}
      connection={connection} onRetry={onRetry} navigate={navigate} />
    <div className="app-content">
      <div hidden={page !== "documents"}><Library csrfToken={session.csrf_token} disabled={locked} onBusy={updateBusy} onDirty={setFileDirty} onSaved={saved} onOpen={identity => go(`/editor/${identity}`)} refreshRevision={usageRevision} tab={libraryTab} onTabChange={setLibraryTab} /></div>
      {opened && <div hidden={page !== "editor"}><Workspace key={opened} identity={opened} dirty={editorDirty} onDirty={setEditorDirty} operationsPaused={locked} authPaused={authPaused} csrfToken={session.csrf_token} onBack={() => go("/documents")} onOpenResource={identity => go(`/editor/${identity}`)} onChanged={saved} onBusy={updateBusy} /></div>}
      <div hidden={page !== "profile"}><Profile user={session.user} csrfToken={session.csrf_token} onSession={accept} onBusy={updateBusy} disabled={locked} usageRevision={usageRevision} /></div>
    </div>
  </div>;
}
