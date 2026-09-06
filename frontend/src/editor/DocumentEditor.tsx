import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { mountEditor, type EditorAdapter, type EditorPresentation } from "./adapter";
import { ReviewPanel } from "./ReviewPanel";
import "prosemirror-view/style/prosemirror.css";
import "./editor.css";

export function DocumentEditor({
  initialDocument,
  onDocumentChange,
  discoverySnapshot,
  sourceVersion,
  onReopen,
}: {
  initialDocument: object;
  onDocumentChange?: (document: object) => void;
  discoverySnapshot?: components["schemas"]["FieldSnapshot"] | null;
  sourceVersion?: string;
  onReopen?: () => void;
}) {
  const { t } = useTranslation();
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorAdapter | null>(null);
  const initial = useRef(initialDocument);
  const change = useRef(onDocumentChange);
  change.current = onDocumentChange;
  const [presentation, setPresentation] = useState<EditorPresentation>({ fields: [], active: "", review: null, unsupported: false });
  const { fields: occurrences, active, review, unsupported } = presentation;
  const [label, setLabel] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [reviewStale, setReviewStale] = useState(false);
  useEffect(() => {
    const editor = mountEditor(host.current!, initial.current, {
      onChange: snapshot => change.current?.(snapshot.document),
      onUpdate: setPresentation,
    });
    view.current = editor;
    return () => { editor.destroy(); view.current = null; };
  }, []);
  useEffect(() => { view.current!.setDocumentLabel(t("editor.document")); }, [t]);
  useEffect(() => {
    if (discoverySnapshot && sourceVersion) setReviewStale(!view.current!.attachDiscovery(discoverySnapshot, sourceVersion));
  }, [discoverySnapshot, sourceVersion]);

  return (
    <div className="document-workbench">
      <div className="document-tools">
        <label>
          {t("editor.fieldLabel")}
          <input
            value={label}
            onChange={(event) => setLabel(event.target.value)}
          />
        </label>
        <button
          onClick={() => setInvalid(!view.current!.createField(label))}
        >
          {t("editor.createField")}
        </button>
        <button
          onClick={() => view.current!.undo()}
        >
          {t("editor.undo")}
        </button>
        <button
          onClick={() => view.current!.redo()}
        >
          {t("editor.redo")}
        </button>
        {invalid && <p role="alert">{t("editor.invalidSelection")}</p>}
        {unsupported && <p>{t("editor.unsupported")}</p>}
      </div>
      <div ref={host} className="document-canvas" />
      <aside aria-label={t("editor.fields")}>
        {reviewStale && <div role="alert"><p>{t("review.stale")}</p>{onReopen && <button type="button" onClick={onReopen}>{t("review.reopen")}</button>}</div>}
        {review && <details className="review-section"><summary>{t("review.title")}</summary>
          <ReviewPanel review={review} occurrences={occurrences} act={(id, action, options) => view.current!.review(id, action, options)} />
        </details>}
        {occurrences.map((field) => (
          <div key={field.id} data-active={active === field.id}>
            <label>
              {field.label}
              <input
                aria-label={t("editor.fieldValue", { label: field.label })}
                value={field.value}
                onChange={event => view.current!.updateField(field.key, event.target.value)}
              />
            </label>
            <button
              onClick={() => view.current!.focusField(field.id)}
            >
              {t("editor.focus", { label: field.label })}
            </button>
            <button
              onClick={() => view.current!.removeField(field.id)}
            >
              {t("editor.remove", { label: field.label })}
            </button>
            {occurrences.some(
              (other) => other.key === field.key && other.value !== field.value,
            ) && <p role="status">{t("editor.inconsistent")}</p>}
          </div>
        ))}
      </aside>
    </div>
  );
}
