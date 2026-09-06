import { useCallback, useEffect, useState, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Session } from "./accounts/Authentication";
import { Profile } from "./accounts/Profile";
import { Library } from "./library/Library";

function currentPage() { return window.location.pathname === "/profile" ? "profile" : "documents"; }

export function SessionPages({ session, accept, authBusy, setAuthBusy }: {
  session: Session; accept: (session: Session) => void; authBusy: boolean;
  setAuthBusy: (busy: boolean) => void;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(currentPage);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [usageRevision, setUsageRevision] = useState(0);
  const updateBusy = useCallback((value: boolean) => { setBusy(value); setAuthBusy(value); }, [setAuthBusy]);
  const saved = useCallback(() => setUsageRevision(value => value + 1), []);
  useEffect(() => {
    if (!["/documents", "/profile"].includes(window.location.pathname)) window.history.replaceState(null, "", "/documents");
    const pop = () => setPage(currentPage());
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  useEffect(() => {
    if (!busy && !dirty) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [busy, dirty]);
  function navigate(event: MouseEvent<HTMLAnchorElement>, destination: string) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (busy || authBusy) return;
    window.history.pushState(null, "", `/${destination}`); setPage(destination);
  }
  if (!session.user) return null;
  return <>
    <nav className="page-nav" aria-label={t("navigation.label")}>
      <a href="/documents" aria-current={page === "documents" ? "page" : undefined} aria-disabled={busy || authBusy} onClick={event => navigate(event, "documents")}>{t("library.title")}</a>
      <a href="/profile" aria-current={page === "profile" ? "page" : undefined} aria-disabled={busy || authBusy} onClick={event => navigate(event, "profile")}>{t("profile.title")}</a>
    </nav>
    <div hidden={page !== "documents"}><Library csrfToken={session.csrf_token} disabled={busy || authBusy} onBusy={updateBusy} onDirty={setDirty} onSaved={saved} /></div>
    <div hidden={page !== "profile"}><Profile user={session.user} csrfToken={session.csrf_token} onSession={accept} onBusy={updateBusy} disabled={busy || authBusy} usageRevision={usageRevision} /></div>
  </>;
}
