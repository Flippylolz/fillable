import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { api, apiErrorMessage } from "../api";
import { formatNumber } from "../i18n";
import type { Session } from "./Authentication";
import "./profile.css";

type User = components["schemas"]["UserInfo"];
type Usage = components["schemas"]["QuotaUsage"];

export function Profile({ user, csrfToken, onSession, onBusy, disabled }: {
  user: User; csrfToken: string; onSession: (session: Session) => void;
  onBusy: (busy: boolean) => void; disabled: boolean;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState(user.display_name);
  const [language, setLanguageChoice] = useState(user.ui_language);
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [usageError, setUsageError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const lifetime = useRef(new AbortController());

  useEffect(() => {
    lifetime.current = new AbortController();
    return () => { lifetime.current.abort(); onBusy(false); };
  }, [onBusy]);

  useEffect(() => {
    const controller = new AbortController();
    setUsage(null);
    setUsageError("");
    void api.GET("/api/storage/usage", { signal: controller.signal })
      .then(result => {
        if (controller.signal.aborted) return;
        if (result.data) setUsage(result.data);
        else setUsageError(result.error.error.code);
      })
      .catch(() => { if (!controller.signal.aborted) setUsageError("internal_error"); });
    return () => controller.abort();
  }, [user.id, attempt]);

  async function submit(kind: "name" | "password" | "language", event: FormEvent) {
    event.preventDefault();
    if (busy || disabled) return;
    setError(""); setNotice("");
    if (kind === "password" && password !== confirmation) {
      setError("password_mismatch");
      return;
    }
    const controller = lifetime.current;
    setBusy(true); onBusy(true);
    try {
      const options = { headers: { "X-CSRF-Token": csrfToken }, signal: controller.signal };
      const result = kind === "name"
        ? await api.PATCH("/api/profile", { ...options, body: { display_name: name } })
        : kind === "language"
          ? await api.PATCH("/api/profile/language", { ...options, body: { ui_language: language } })
          : await api.POST("/api/profile/password", { ...options, body: { current_password: current, new_password: password } });
      if (controller.signal.aborted) return;
      if (result.data?.user) {
        onSession(result.data);
        if (kind === "name") setName(result.data.user.display_name);
        else if (kind === "password") { setCurrent(""); setPassword(""); setConfirmation(""); }
        setLanguageChoice(result.data.user.ui_language);
        setNotice(kind === "name" ? "profile.nameSaved" : kind === "language" ? "profile.languageSaved" : "profile.passwordSaved");
      } else {
        if (kind === "language") setLanguageChoice(user.ui_language);
        setError(result.error?.error.code ?? "internal_error");
      }
    } catch {
      if (!controller.signal.aborted) {
        if (kind === "language") setLanguageChoice(user.ui_language);
        setError("internal_error");
      }
    } finally {
      if (!controller.signal.aborted) { setBusy(false); onBusy(false); }
    }
  }

  function bytes(value: number) {
    return t("profile.bytes", { count: value, value: formatNumber(value) });
  }

  return <section className="profile" aria-labelledby="profile-title">
    <h2 id="profile-title">{t("profile.title")}</h2>
    {error && <p role="alert">{error === "password_mismatch" ? t("profile.passwordMismatch") : apiErrorMessage(error)}</p>}
    {notice && <p role="status">{t(notice)}</p>}
    <form className="profile-card" aria-labelledby="profile-account" onSubmit={event => void submit("name", event)}>
      <h3 id="profile-account">{t("profile.account")}</h3>
      <label>{t("auth.email")}<input type="email" value={user.email} readOnly /></label>
      <label>{t("profile.displayName")}<input value={name} onChange={event => setName(event.target.value)} required maxLength={120} disabled={busy || disabled} autoComplete="name" /></label>
      <button disabled={busy || disabled} type="submit">{t("profile.saveName")}</button>
    </form>
    <form className="profile-card" aria-labelledby="profile-security" onSubmit={event => void submit("password", event)}>
      <h3 id="profile-security">{t("profile.security")}</h3>
      <p>{t("profile.passwordHint")}</p>
      <label>{t("profile.currentPassword")}<input type="password" value={current} onChange={event => setCurrent(event.target.value)} required maxLength={1024} disabled={busy || disabled} autoComplete="current-password" /></label>
      <label>{t("profile.newPassword")}<input type="password" value={password} onChange={event => setPassword(event.target.value)} required minLength={12} maxLength={1024} disabled={busy || disabled} autoComplete="new-password" /></label>
      <label>{t("profile.confirmPassword")}<input type="password" value={confirmation} onChange={event => setConfirmation(event.target.value)} required minLength={12} maxLength={1024} disabled={busy || disabled} autoComplete="new-password" /></label>
      <button disabled={busy || disabled} type="submit">{t("profile.changePassword")}</button>
    </form>
    <form className="profile-card" aria-labelledby="profile-language" onSubmit={event => void submit("language", event)}>
      <h3 id="profile-language">{t("profile.language")}</h3>
      <label>{t("profile.language")}<select value={language} onChange={event => setLanguageChoice(event.target.value === "en" ? "en" : "uk")} disabled={busy || disabled}>
        <option value="uk">{t("profile.languageUk")}</option>
        <option value="en">{t("profile.languageEn")}</option>
      </select></label>
      <button type="submit" disabled={busy || disabled}>{t("profile.saveLanguage")}</button>
    </form>
    <section className="profile-card profile-storage" aria-labelledby="profile-storage">
      <h3 id="profile-storage">{t("profile.storage")}</h3>
      {!usage && !usageError && <p role="status">{t("profile.usageLoading")}</p>}
      {usageError && <p role="alert">{apiErrorMessage(usageError)}</p>}
      {usage && <>
        <dl>
          <dt>{t("profile.used")}</dt><dd>{bytes(usage.used_bytes)}</dd>
          <dt>{t("profile.limit")}</dt><dd>{bytes(usage.limit_bytes)}</dd>
          <dt>{t("profile.available")}</dt><dd>{bytes(usage.available_bytes)}</dd>
          <dt>{t("profile.reserved")}</dt><dd>{bytes(usage.reserved_bytes)}</dd>
        </dl>
        {usage.over_limit && <p role="status">{t("profile.overLimit")}</p>}
      </>}
      <button type="button" onClick={() => setAttempt(value => value + 1)}>{t("profile.refreshUsage")}</button>
    </section>
  </section>;
}
