import { useId } from "react";
import { useTranslation } from "react-i18next";
import type { FieldSummary } from "./adapter";
import { FIELD_VALUE_LIMIT } from "./fieldValues";
import { formatDateValue, parseDateValue } from "./fieldKinds";

/** The typed field entry control shared by the sidebar cards and the fill form. */
export function FieldInput({ field, readOnly, update, compact }: {
  field: FieldSummary; readOnly: boolean; update: (key: string, value: string) => void;
  compact?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const numbers = new Intl.NumberFormat(i18n.resolvedLanguage);
  const errorId = useId();
  const described = field.issue ? errorId : undefined;
  // Number values keep the user's exact text (comma decimals included);
  // the picker writes the canonical ДД.ММ.РРРР document format.
  const control = field.type === "date"
    ? <input type="date" disabled={readOnly} value={parseDateValue(field.value) ?? ""}
      aria-label={t("editor.fieldValue", { label: field.label })}
      aria-invalid={field.issue ? true : undefined} aria-describedby={described}
      onChange={event => update(field.key, formatDateValue(event.target.value) ?? "")} />
    : field.type === "number"
      ? <input type="text" inputMode="decimal" disabled={readOnly} value={field.value}
        aria-label={t("editor.fieldValue", { label: field.label })}
        aria-invalid={field.issue ? true : undefined} aria-describedby={described}
        onChange={event => update(field.key, event.target.value)} />
      // Compact cards start at the content's line count instead of a tall fixed box.
      : <textarea disabled={readOnly} rows={compact ? Math.min(4, Math.max(1, field.value.split("\n").length)) : 3} aria-label={t("editor.fieldValue", { label: field.label })} value={field.value}
        aria-invalid={field.issue ? true : undefined} aria-describedby={described}
        onChange={event => update(field.key, event.target.value)} />;
  return <>
    {control}
    {field.issue && <p role="alert" id={errorId} className="field-conflict">{t(`editor.value.${field.issue}`, { limit: numbers.format(FIELD_VALUE_LIMIT) })}</p>}
  </>;
}
