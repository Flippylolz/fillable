import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, apiErrorMessage } from "../api";
import type { Session } from "./Authentication";

export function Reauthentication({ owner, onRecovered, allowDiscard }: {
  owner: NonNullable<Session["user"]>; onRecovered: (session: Session) => void; allowDiscard: () => boolean;
}) {
  const { t } = useTranslation();
  const [fresh, setFresh] = useState<Session | null>(null), [password, setPassword] = useState("");
  const [busy, setBusy] = useState(true), [error, setError] = useState(""), [attempt, setAttempt] = useState(0);
  const callbacks = useRef({ onRecovered, allowDiscard }); callbacks.current = { onRecovered, allowDiscard };
  const lifetime = useRef(new AbortController()), running = useRef(false);
  useEffect(() => { const controller = new AbortController(); lifetime.current = controller; return () => controller.abort(); }, []);
  useEffect(() => {
    const controller = new AbortController(); let alive = true;
    const timeout = setTimeout(() => controller.abort(), 10000);
    setBusy(true); setError(""); setFresh(null);
    void api.GET("/api/auth/session", { signal: controller.signal }).then(result => {
      if (!alive || controller.signal.aborted) return;
      if (result.data) {
        if (result.data.user?.id === owner.id) callbacks.current.onRecovered(result.data);
        else { setFresh(result.data); if (result.data.user) setError("different_account"); }
      } else setError(result.error.error.code);
    }).catch(() => { if (alive) setError("internal_error"); })
      .finally(() => { clearTimeout(timeout); if (alive) setBusy(false); });
    return () => { alive = false; clearTimeout(timeout); controller.abort(); };
  }, [owner.id, attempt]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!fresh || busy || running.current) return;
    running.current = true; setBusy(true); setError("");
    const controller = new AbortController(), session = lifetime.current;
    const cancel = () => controller.abort(); session.signal.addEventListener("abort", cancel, { once: true });
    const timeout = setTimeout(cancel, 10000);
    try {
      const result = await api.POST("/api/auth/login", { headers: { "X-CSRF-Token": fresh.csrf_token },
        body: { login: owner.login, password }, signal: controller.signal });
      if (session.signal.aborted || controller.signal.aborted) return;
      if (result.data) {
        setPassword("");
        if (result.data.user?.id === owner.id) callbacks.current.onRecovered(result.data);
        else { setFresh(result.data); setError("different_account"); }
      } else {
        setError(result.error.error.code);
        if (["authentication_required", "forbidden"].includes(result.error.error.code)) setFresh(null);
      }
    } catch { if (!session.signal.aborted) setError("internal_error"); }
    finally {
      clearTimeout(timeout); session.signal.removeEventListener("abort", cancel);
      if (!session.signal.aborted) { running.current = false; setBusy(false); }
    }
  }
  function switchAccount() {
    if (fresh && !busy && callbacks.current.allowDiscard()) callbacks.current.onRecovered(fresh);
  }
  return <section className="reauthentication" aria-label={t("reauth.title")} aria-busy={busy}>
    <h2>{t("reauth.title")}</h2><p>{t("reauth.kept")}</p>
    {error && <p role="alert">{error === "different_account" ? t("reauth.different") : apiErrorMessage(error)}</p>}
    {busy && <p role="status">{t("auth.loading")}</p>}
    {!fresh && !busy && <button type="button" onClick={() => setAttempt(value => value + 1)}>{t("auth.retry")}</button>}
    {fresh && <><form onSubmit={event => void submit(event)}>
      <label>{t("auth.identifier")}<input type="text" value={owner.login} readOnly autoComplete="username" /></label>
      <label>{t("auth.password")}<input type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={event => setPassword(event.target.value)} /></label>
      <button type="submit" disabled={busy}>{t("reauth.action")}</button>
    </form><button type="button" disabled={busy} onClick={switchAccount}>{fresh.user ? t("reauth.other", { login: fresh.user.login }) : t("reauth.switch")}</button></>}
  </section>;
}
