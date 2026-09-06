import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { mountEditor, type EditorAdapter, type EditorPresentation } from "./adapter";
import { ReviewPanel } from "./ReviewPanel";
import { FieldSidebar } from "./FieldSidebar";
import "prosemirror-view/style/prosemirror.css";
import "./editor.css";

export function DocumentEditor({
  initialDocument,
  onDocumentChange,
  onFieldValidityChange,
  discoverySnapshot,
  sourceVersion,
  onReopen,
}: {
  initialDocument: object;
  onDocumentChange?: (document: object) => void;
  onFieldValidityChange?: (valid: boolean) => void;
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
  const validity = useRef(onFieldValidityChange);
  validity.current = onFieldValidityChange;
  const [presentation, setPresentation] = useState<EditorPresentation>({ fields: [], active: "", review: null, unsupported: false, fieldValuesValid: true });
  const { fields: occurrences, active, review, unsupported } = presentation;
  const [label, setLabel] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [reviewStale, setReviewStale] = useState(false);
  useEffect(() => {
    const editor = mountEditor(host.current!, initial.current, {
      onChange: snapshot => change.current?.(snapshot.document),
      onUpdate: presentation => { setPresentation(presentation); validity.current?.(presentation.fieldValuesValid); },
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
        <FieldSidebar fields={occurrences} active={active}
          update={(key, value) => { view.current!.updateField(key, value); }}
          focus={id => { view.current!.focusField(id); }} remove={id => { view.current!.removeField(id); }} />
      </aside>
    </div>
  );
}
