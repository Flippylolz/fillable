import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { FieldOccurrence } from "./model";
import type { ReviewItem, ReviewState } from "./review";
import "./review.css";

export type ReviewAction = "accept" | "dismiss" | "configure" | "focus";
type Options = { label: string; key: string; type: string };
type Group = { key: string; label: string };
function ReviewCard({ item, groups, act }: { item: ReviewItem; groups: Group[];
  act: (id: string, action: ReviewAction, options: Options) => boolean }) {
  const { t, i18n } = useTranslation();
  const numbers = new Intl.NumberFormat(i18n.resolvedLanguage);
  const [label, setLabel] = useState(item.label), [key, setKey] = useState(item.key);
  const [invalid, setInvalid] = useState(false);
  useEffect(() => { setLabel(item.label); setKey(item.key); }, [item.label, item.key]);
  function apply(action: ReviewAction) {
    setInvalid(!act(item.id, action, { label, key, type: "text" }));
  }
  return <article className="review-card" aria-label={t("review.card", { label: item.label })}>
    <p className="review-reason">{t(`review.reason.${item.reason}`)}</p>
    <p className="review-context">{item.context}</p>
    {item.missing && <p role="status" className="review-missing">{t("review.missing")}</p>}
    <label>{t("review.label")}<input value={label} disabled={item.missing} onChange={event => setLabel(event.target.value)} /></label>
    <label>{t("review.type")}<select defaultValue="text" disabled={item.missing}><option value="text">{t("review.text")}</option></select></label>
    <label>{t("review.group")}<select value={key} disabled={item.missing} onChange={event => setKey(event.target.value)}>
      <option value="">{t("review.independent")}</option>
      {key && !groups.some(group => group.key === key) && <option value={key}>{t("review.sourceGroup")}</option>}
      {groups.map((group, index) => <option key={group.key} value={group.key}>{t("review.groupOption", { label: group.label, number: numbers.format(index + 1) })}</option>)}
    </select></label>
    {invalid && <p role="alert">{t("review.invalid")}</p>}
    <div className="review-actions">
      <button type="button" disabled={item.missing} onClick={() => apply("focus")}>{t("review.focus")}</button>
      <button type="button" disabled={item.missing} onClick={() => apply("configure")}>{t("review.apply")}</button>
      {item.decision !== "accepted" && <><button type="button" className="review-accept" disabled={item.missing} onClick={() => apply("accept")}>{t("review.accept")}</button>
        {item.decision !== "dismissed" && <button type="button" onClick={() => apply("dismiss")}>{t("review.dismiss")}</button>}</>}
    </div>
  </article>;
}

export function ReviewPanel({ review, occurrences, act }: { review: ReviewState; occurrences: FieldOccurrence[];
  act: (id: string, action: ReviewAction, options: Options) => boolean }) {
  const { t, i18n } = useTranslation();
  const numbers = new Intl.NumberFormat(i18n.resolvedLanguage);
  const [filter, setFilter] = useState<ReviewItem["decision"]>("proposed"), [page, setPage] = useState(0);
  const items = review.items.filter(item => item.decision === filter);
  const pages = Math.max(1, Math.ceil(items.length / 10)), current = Math.min(page, pages - 1);
  const indexed = new Map<string, Group>();
  for (const field of occurrences) if (!indexed.has(field.key)) indexed.set(field.key, { key: field.key, label: field.label });
  const groups = [...indexed.values()];
  const countLabel = (decision: ReviewItem["decision"]) => {
    const count = review.items.filter(item => item.decision === decision).length;
    return t(`review.${decision}`, { count, formattedCount: numbers.format(count) });
  };
  return <section className="field-review" aria-label={t("review.title")}>
    <p className="review-draft-note">{t("review.draft")}</p>
    <label>{t("review.filter")}<select value={filter} onChange={event => { setFilter(event.target.value as ReviewItem["decision"]); setPage(0); }}>
      <option value="proposed">{countLabel("proposed")}</option>
      <option value="accepted">{countLabel("accepted")}</option>
      <option value="dismissed">{countLabel("dismissed")}</option>
    </select></label>
    {!items.length && <p>{t("review.empty")}</p>}
    {items.slice(current * 10, (current + 1) * 10).map(item => <ReviewCard key={item.id} item={item} groups={groups} act={act} />)}
    {pages > 1 && <div className="review-pages"><button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>{t("review.previous")}</button>
      <span>{t("review.page", { current: numbers.format(current + 1), total: numbers.format(pages) })}</span>
      <button type="button" disabled={current === pages - 1} onClick={() => setPage(current + 1)}>{t("review.next")}</button></div>}
  </section>;
}
