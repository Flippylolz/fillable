import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Session } from "./accounts/Authentication";
import { Profile } from "./accounts/Profile";
import { Library } from "./library/Library";
import { Workspace } from "./workspace/Workspace";

function route(path: string) {
  const match = /^\/editor\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(path);
  return { page: match ? "editor" : path === "/profile" ? "profile" : "documents", identity: match?.[1] ?? null };
}
export function SessionPages({ session, accept, authBusy, setAuthBusy, setLeaveGuard, authPaused = false }: {
  authPaused?: boolean;
  session: Session; accept: (session: Session) => void; authBusy: boolean;
  setAuthBusy: (busy: boolean) => void; setLeaveGuard?: (guard: () => boolean) => void;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(() => route(window.location.pathname).page);
  const [opened, setOpened] = useState(() => route(window.location.pathname).identity);
  const [busy, setBusy] = useState(false);
  const [fileDirty, setFileDirty] = useState(false);
  const [editorDirty, setEditorDirty] = useState(false);
  const [usageRevision, setUsageRevision] = useState(0);
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
  if (!session.user) return null;
  return <>
    <nav className="page-nav" aria-label={t("navigation.label")}>
      <a href="/documents" aria-current={page === "documents" ? "page" : undefined} aria-disabled={busy || authBusy || authPaused} onClick={event => navigate(event, "/documents")}>{t("library.title")}</a>
      {opened && <a href={`/editor/${opened}`} aria-current={page === "editor" ? "page" : undefined} aria-disabled={busy || authBusy || authPaused} onClick={event => navigate(event, `/editor/${opened}`)}>{t("workspace.title")}</a>}
      <a href="/profile" className="page-nav-account" aria-current={page === "profile" ? "page" : undefined} aria-disabled={busy || authBusy || authPaused} onClick={event => navigate(event, "/profile")}>{t("profile.title")}</a>
    </nav>
    <div hidden={page !== "documents"}><Library csrfToken={session.csrf_token} disabled={busy || authBusy || authPaused} onBusy={updateBusy} onDirty={setFileDirty} onSaved={saved} onOpen={identity => go(`/editor/${identity}`)} refreshRevision={usageRevision} /></div>
    {opened && <div hidden={page !== "editor"}><Workspace key={opened} identity={opened} dirty={editorDirty} onDirty={setEditorDirty} operationsPaused={busy || authBusy || authPaused} authPaused={authPaused} csrfToken={session.csrf_token} onBack={() => go("/documents")} onOpenResource={identity => go(`/editor/${identity}`)} onChanged={saved} onBusy={updateBusy} /></div>}
    <div hidden={page !== "profile"}><Profile user={session.user} csrfToken={session.csrf_token} onSession={accept} onBusy={updateBusy} disabled={busy || authBusy || authPaused} usageRevision={usageRevision} /></div>
  </>;
}
