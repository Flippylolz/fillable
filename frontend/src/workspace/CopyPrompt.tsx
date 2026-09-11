import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { apiErrorMessage } from "../api";

/** The save-to-documents name prompt; the parent owns the copy request. */
export function CopyPrompt({ initialTitle, busy, error, disabled = false, onSubmit, onCancel }: {
  initialTitle: string; busy: boolean; error: string; disabled?: boolean;
  onSubmit: (title: string) => void; onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [title, setTitle] = useState(initialTitle);
  const [issue, setIssue] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || disabled) return;
    if (!title.trim()) { setIssue("invalid_request"); return; }
    setIssue("");
    onSubmit(title.trim());
  }
  return <form className="workspace-copy" aria-label={t("workspace.saveToDocuments")} onSubmit={submit}>
    <p>{t("workspace.copyDescription")}</p>
    <label>{t("copy.title")}
      <input autoFocus maxLength={160} value={title} disabled={busy || disabled}
        onChange={event => { setTitle(event.target.value); setIssue(""); }} />
    </label>
    <button type="submit" className="primary" disabled={busy || disabled}>{t(busy ? "copy.creating" : "workspace.copyCreate")}</button>
    <button type="button" disabled={busy || disabled} onClick={onCancel}>{t("copy.cancel")}</button>
    {(issue || error) && <p role="alert">{apiErrorMessage(issue || error)}</p>}
  </form>;
}
