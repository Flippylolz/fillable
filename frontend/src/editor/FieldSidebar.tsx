import { useTranslation } from "react-i18next";
import type { FieldSummary } from "./adapter";
import "./sidebar.css";

export function FieldSidebar({ fields, active, update, focus, remove }: {
  fields: FieldSummary[]; active: string;
  update: (key: string, value: string) => void;
  focus: (id: string) => void; remove: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const numbers = new Intl.NumberFormat(i18n.resolvedLanguage);
  const index = fields.findIndex(field => field.id === active);
  return <section className="field-sidebar" aria-label={t("editor.values")}>
    <h3>{t("editor.values")}</h3>
    {!fields.length ? <p>{t("editor.noFields")}</p> : <>
      <div className="field-navigation" role="group" aria-label={t("editor.navigation")}>
        <p role="status">{index < 0 ? t("editor.chooseLocation") : t("editor.position", { current: numbers.format(index + 1), total: numbers.format(fields.length) })}</p>
        <button type="button" disabled={index === 0} onClick={() => focus(fields[index < 0 ? fields.length - 1 : index - 1].id)}>{t("editor.previousField")}</button>
        <button type="button" disabled={index === fields.length - 1} onClick={() => focus(fields[index + 1].id)}>{t("editor.nextField")}</button>
      </div>
      {fields.map((field, number) => <article key={field.id} className="field-value-card" data-active={active === field.id}
        aria-current={active === field.id ? true : undefined}
        aria-label={t("editor.occurrence", { number: numbers.format(number + 1), label: field.label })}>
        <p className="field-type">{t("review.text")}</p>
        {active === field.id && <p className="field-active">{t("editor.activeField")}</p>}
        <label>{field.label}<input aria-label={t("editor.fieldValue", { label: field.label })} value={field.value}
          onChange={event => update(field.key, event.target.value)} /></label>
        <div className="field-actions">
          <button type="button" onClick={() => focus(field.id)}>{t("editor.focus", { label: field.label })}</button>
          <button type="button" onClick={() => remove(field.id)}>{t("editor.remove", { label: field.label })}</button>
        </div>
        {fields.some(other => other.key === field.key && other.value !== field.value) && <p role="status" className="field-conflict">{t("editor.inconsistent")}</p>}
      </article>)}
    </>}
  </section>;
}
