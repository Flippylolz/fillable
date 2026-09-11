import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { mountEditor, type EditorAdapter, type EditorPresentation, type EditorSnapshot, type FieldSummary } from "./adapter";
import { PAGE_BREAK_CLASS } from "./pagination";
import { ReviewPanel } from "./ReviewPanel";
import { FieldSidebar } from "./FieldSidebar";
import { FillForm } from "./FillForm";
import { FIELD_LABEL_LIMIT, FIELD_RECORD_LIMIT } from "./fieldProperties";
import "prosemirror-view/style/prosemirror.css";
import "./editor.css";
import { useSourceLayout, type SourcePresentation } from "./SourceLayout";

/** The rendered canvas plus its scoped presentation rules, for print-only output. */
export type PrintSource = { node: HTMLElement; rules: string; scope: string };

export function DocumentEditor({
  initialDocument,
  sourcePresentation,
  mode = "document",
  onDocumentChange,
  onSnapshot,
  onReader,
  onFieldsReader,
  onPrintReader,
  reviewSaved = false,
  onFieldValidityChange,
  onCompositionChange,
  discoverySnapshot,
  sourceVersion,
  onReopen,
  canEdit,
  readOnly = false,
  zoom = 1,
  highlight = true,
}: {
  initialDocument: object;
  sourcePresentation?: SourcePresentation;
  mode?: "document" | "fill";
  onDocumentChange?: (document: object) => void;
  onSnapshot?: (snapshot: EditorSnapshot) => void;
  onReader?: (read: (() => EditorSnapshot) | null) => void;
  onFieldsReader?: (read: (() => FieldSummary[]) | null) => void;
  onPrintReader?: (read: (() => PrintSource | null) | null) => void;
  reviewSaved?: boolean;
  onFieldValidityChange?: (valid: boolean) => void;
  onCompositionChange?: (composing: boolean) => void;
  discoverySnapshot?: components["schemas"]["FieldSnapshot"] | null;
  sourceVersion?: string;
  onReopen?: () => void;
  canEdit?: () => boolean;
  readOnly?: boolean;
  zoom?: number;
  highlight?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const layout = useSourceLayout(sourcePresentation);
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorAdapter | null>(null);
  const initial = useRef(initialDocument);
  const access = useRef({ canEdit, readOnly }); access.current = { canEdit, readOnly };
  const change = useRef(onDocumentChange);
  change.current = onDocumentChange;
  const snapshots = useRef({ onSnapshot, onReader, onFieldsReader, onPrintReader }); snapshots.current = { onSnapshot, onReader, onFieldsReader, onPrintReader };
  const fields = useRef<FieldSummary[]>([]);
  const layoutRef = useRef(layout); layoutRef.current = layout;
  const validity = useRef(onFieldValidityChange);
  validity.current = onFieldValidityChange;
  const composition = useRef(onCompositionChange);
  composition.current = onCompositionChange;
  const [presentation, setPresentation] = useState<EditorPresentation>({ fields: [], active: "", review: null, unsupported: false, fieldValuesValid: true, composing: false, glyphCheckbox: false, canUndo: false, canRedo: false });
  const { fields: occurrences, active, review, unsupported, glyphCheckbox, canUndo, canRedo } = presentation;
  const [date, setDate] = useState("");
  const [dateIssue, setDateIssue] = useState<ReturnType<EditorAdapter["fillDate"]>>(null);
  const dateHelp = useId();
  const [checkboxIssue, setCheckboxIssue] = useState<ReturnType<EditorAdapter["toggleGlyph"]>>(null);
  const checkboxHelp = useId();
  const [label, setLabel] = useState("");
  const [creationIssue, setCreationIssue] = useState<ReturnType<EditorAdapter["createField"]>>(null);
  const creationErrorId = useId();
  const [reviewStale, setReviewStale] = useState(false);
  const previewHost = useRef<HTMLDivElement | null>(null);
  const [previewTick, setPreviewTick] = useState(0);
  useEffect(() => {
    const editor = mountEditor(host.current!, initial.current, {
      presentation: sourcePresentation,
      canEdit: () => !access.current.readOnly && access.current.canEdit?.() !== false,
      onChange: snapshot => { change.current?.(snapshot.document); snapshots.current.onSnapshot?.(snapshot); },
      onUpdate: presentation => {
        fields.current = presentation.fields; setPresentation(presentation);
        validity.current?.(presentation.fieldValuesValid); composition.current?.(presentation.composing);
      },
    });
    view.current = editor;
    snapshots.current.onReader?.(editor.exportSnapshot);
    snapshots.current.onFieldsReader?.(() => fields.current);
    snapshots.current.onPrintReader?.(() => {
      const node = host.current?.querySelector<HTMLElement>(".ProseMirror");
      return node ? { node, rules: layoutRef.current.rules, scope: layoutRef.current.scope } : null;
    });
    return () => { snapshots.current.onReader?.(null); snapshots.current.onFieldsReader?.(null); snapshots.current.onPrintReader?.(null); editor.destroy(); view.current = null; };
  }, []);
  useEffect(() => { view.current!.refreshAccess(); }, [readOnly, canEdit]);
  useEffect(() => {
    view.current!.setDocumentLabel(t("editor.document"));
    view.current!.setPageBreakLabel(page => t("editor.pageBreak", { page }));
    view.current!.setShapeCheckboxLabel(t("editor.shapeCheckbox"));
  }, [t]);
  useEffect(() => {
    if (discoverySnapshot && sourceVersion) setReviewStale(!view.current!.attachDiscovery(discoverySnapshot, sourceVersion, reviewSaved));
  }, [discoverySnapshot, sourceVersion, reviewSaved]);
  // The fill mode's preview follows the live document with a bounded refresh.
  useEffect(() => {
    if (mode !== "fill") return;
    const timer = setTimeout(() => setPreviewTick(value => value + 1), 700);
    return () => clearTimeout(timer);
  }, [mode, presentation]);
  useEffect(() => {
    if (mode !== "fill" || !previewHost.current) return;
    const canvas = host.current?.querySelector(".ProseMirror");
    if (!canvas) return;
    const clone = canvas.cloneNode(true) as HTMLElement;
    clone.querySelectorAll(`.${PAGE_BREAK_CLASS}`).forEach(marker => marker.remove());
    previewHost.current.innerHTML = "";
    previewHost.current.appendChild(clone);
  }, [previewTick, mode]);
  // Returning from the hidden canvas recomputes the visual page breaks.
  useEffect(() => {
    if (mode !== "fill") view.current!.setPageBreakLabel(page => t("editor.pageBreak", { page }));
  }, [mode, t]);

  return (
    <div className="document-workbench" data-highlight-fields={highlight} data-mode={mode} style={{ "--document-zoom": zoom } as CSSProperties}>
      {mode === "fill" && <div className="fill-layout">
        <style>{layout.rules}</style>
        {reviewStale && <div role="alert" className="fill-review-stale"><p>{t("review.stale")}</p>{onReopen && <button type="button" onClick={onReopen}>{t("review.reopen")}</button>}</div>}
        <FillForm fields={occurrences} active={active} readOnly={readOnly}
          update={(key, value) => { view.current!.updateField(key, value); }}
          focus={id => { view.current!.focusField(id); }} remove={id => { view.current!.removeField(id); }}
          undo={() => view.current!.undo()} redo={() => view.current!.redo()} canUndo={canUndo} canRedo={canRedo} />
        <div className="fill-preview" data-layout={layout.scope} aria-hidden="true">
          <div className="fill-preview-content" ref={previewHost} />
        </div>
      </div>}
      <div className="document-tools">
        <label>
          {t("editor.fieldLabel")}
          <input
            aria-invalid={creationIssue === "invalid_label" || undefined}
            aria-describedby={creationIssue === "invalid_label" ? creationErrorId : undefined}
            disabled={readOnly}
            value={label}
            onChange={(event) => setLabel(event.target.value)}
          />
        </label>
        <button disabled={readOnly}
          onClick={() => setCreationIssue(view.current!.createField(label))}
        >
          {t("editor.createField")}
        </button>
        <button disabled={readOnly || !canUndo}
          onClick={() => view.current!.undo()}
        >
          {t("editor.undo")}
        </button>
        <button disabled={readOnly || !canRedo}
          onClick={() => view.current!.redo()}
        >
          {t("editor.redo")}
        </button>
        <label>{t("editor.boxedDate")}
          <input type="date" value={date} disabled={readOnly} aria-describedby={dateHelp}
            onChange={event => { setDate(event.target.value); setDateIssue(null); }} />
        </label>
        <button disabled={readOnly || !date} onClick={() => setDateIssue(view.current!.fillDate(date))}>{t("editor.fillDateBoxes")}</button>
        <p id={dateHelp}>{t("editor.dateBoxesHelp")}</p>
        {dateIssue && <p role="alert">{t(`editor.dateBoxes.${dateIssue}`)}</p>}
        <button disabled={readOnly || !glyphCheckbox} onClick={() => setCheckboxIssue(view.current!.toggleGlyph())}>{t("editor.toggleCheckbox")}</button>
        <p id={checkboxHelp}>{t("editor.checkboxHelp")}</p>
        {checkboxIssue && <p role="alert">{t(`editor.checkbox.${checkboxIssue}`)}</p>}
        {creationIssue && <p role="alert" id={creationErrorId}>{t(`editor.creation.${creationIssue}`, { labelLimit: new Intl.NumberFormat(i18n.resolvedLanguage).format(FIELD_LABEL_LIMIT), fieldLimit: new Intl.NumberFormat(i18n.resolvedLanguage).format(FIELD_RECORD_LIMIT) })}</p>}
        {unsupported && <p>{t("editor.unsupported")}</p>}
      </div>
      <style>{layout.rules}</style>
      <div ref={host} className="document-canvas" data-layout={layout.scope} />
      <aside aria-label={t("editor.fields")}>
        {reviewStale && <div role="alert"><p>{t("review.stale")}</p>{onReopen && <button type="button" onClick={onReopen}>{t("review.reopen")}</button>}</div>}
        {review && <details className="review-section"><summary>{t("review.title")}</summary>
          <ReviewPanel readOnly={readOnly} review={review} occurrences={occurrences} act={(id, action, options) => view.current!.review(id, action, options)} />
        </details>}
        <FieldSidebar readOnly={readOnly} fields={occurrences} active={active}
          update={(key, value) => { view.current!.updateField(key, value); }}
          focus={id => { view.current!.focusField(id); }} remove={id => { view.current!.removeField(id); }} />
      </aside>
    </div>
  );
}
