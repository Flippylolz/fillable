import { useTranslation } from "react-i18next";
import type { FieldSummary } from "./adapter";
import { FieldInput } from "./FieldInput";
import "./fill.css";

/** The filling-focused form: the working fields in document order. */
export function FillForm({ fields, active, update, focus, remove, readOnly, undo, redo, canUndo, canRedo }: {
  fields: FieldSummary[]; active: string;
  update: (key: string, value: string) => void;
  focus: (id: string) => void; remove: (id: string) => void;
  readOnly: boolean; undo: () => void; redo: () => void; canUndo: boolean; canRedo: boolean;
}) {
  const { t, i18n } = useTranslation();
  const numbers = new Intl.NumberFormat(i18n.resolvedLanguage);
  return <div className="fill-form" aria-label={t("workspace.fillTitle")}>
    <h3>{t("workspace.fillTitle")}</h3>
    <div className="fill-tools">
      <button type="button" disabled={readOnly || !canUndo} onClick={undo}>{t("editor.undo")}</button>
      <button type="button" disabled={readOnly || !canRedo} onClick={redo}>{t("editor.redo")}</button>
    </div>
    {!fields.length ? <p>{t("editor.fillEmpty")}</p> : fields.map((field, number) =>
      <article key={field.id} className="fill-entry" data-active={active === field.id}
        aria-current={active === field.id ? true : undefined}
        aria-label={t("editor.occurrence", { number: numbers.format(number + 1), label: field.label })}>
        <div className="fill-entry-header">
          <h4>{field.label}</h4>
          <span className="field-type">{t(`review.${field.type}`)}</span>
        </div>
        <FieldInput field={field} readOnly={readOnly} update={update} />
        {fields.some(other => other.key === field.key && other.value !== field.value)
          && <p role="status" className="field-conflict">{t("editor.inconsistent")}</p>}
        <div className="fill-entry-actions">
          <button type="button" onClick={() => focus(field.id)}>{t("editor.focus", { label: field.label })}</button>
          <button type="button" disabled={readOnly} onClick={() => remove(field.id)}>{t("editor.remove", { label: field.label })}</button>
        </div>
      </article>)}
  </div>;
}
