import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { api, apiErrorMessage } from "../api";
import { setLanguage } from "../i18n";
import "./authentication.css";

export type Session = components["schemas"]["SessionInfo"];

export function Authentication({
  children,
}: {
  children: (session: Session, actions: {
    accept: (session: Session) => void;
    busy: boolean;
    setBusy: (busy: boolean) => void;
    setLeaveGuard: (guard: () => boolean) => void;
  }) => ReactNode;
}) {
  const { t } = useTranslation();
  const [session, setSession] = useState<Session | null>(null);
  const [busy, setBusy] = useState(true);
  const [childBusy, setChildBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const leaveGuard = useRef<() => boolean>(() => true);
  const setLeaveGuard = useCallback((guard: () => boolean) => { leaveGuard.current = guard; }, []);
  function accept(value: Session) {
    setSession(value);
    if (value.user) void setLanguage(value.user.ui_language);
  }
  useEffect(() => {
    if (session && !session.user) window.history.replaceState(null, "", "/login");
  }, [session]);
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    setError("");
    void api
      .GET("/api/auth/session", { signal: controller.signal })
      .then(({ data, error }) => {
        if (controller.signal.aborted) return;
        if (data) accept(data);
        else setError(apiErrorMessage(error.error.code));
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(apiErrorMessage("internal_error"));
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [attempt]);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!session || busy || childBusy) return;
    if (session.user && !leaveGuard.current()) return;
    setBusy(true);
    setError("");
    try {
      const options = { headers: { "X-CSRF-Token": session.csrf_token } };
      const result = session.user
        ? await api.POST("/api/auth/logout", options)
        : await api.POST("/api/auth/login", {
            ...options,
            body: { email, password },
          });
      if (result.data) {
        accept(result.data);
        setPassword("");
      } else {
        setError(apiErrorMessage(result.error.error.code));
      }
    } catch {
      setError(apiErrorMessage("internal_error"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="authentication"
      aria-label={t("auth.account")}
      aria-busy={busy}
    >
      {error && <p role="alert">{error}</p>}
      {!session && (
        <>
          <p>{t(busy ? "auth.loading" : "auth.unavailable")}</p>
          {!busy && (
            <button onClick={() => setAttempt((value) => value + 1)}>
              {t("auth.retry")}
            </button>
          )}
        </>
      )}
      {session?.user && (
        <>
          <div className="account-strip"><p>{t("auth.signedIn", { name: session.user.display_name })}</p>
          <button disabled={busy || childBusy} onClick={() => void submit()}>
            {t("auth.logout")}
          </button>
          </div>
          {children(session, { accept, busy, setBusy: setChildBusy, setLeaveGuard })}
        </>
      )}
      {session && !session.user && (
        <form onSubmit={(event) => void submit(event)}>
          <h2>{t("auth.login")}</h2>
          <label>
            {t("auth.email")}
            <input
              type="email"
              autoComplete="username"
              required
              maxLength={254}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            {t("auth.password")}
            <input
              type="password"
              autoComplete="current-password"
              required
              maxLength={1024}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button type="submit" disabled={busy}>
            {t("auth.login")}
          </button>
        </form>
      )}
    </section>
  );
}
