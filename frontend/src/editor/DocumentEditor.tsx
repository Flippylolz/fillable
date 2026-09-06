import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { EditorState, type Transaction } from "prosemirror-state";
import { EditorView } from "prosemirror-view";
import { history, undo, redo } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import { baseKeymap } from "prosemirror-commands";
import { editorSchema, fields, type FieldOccurrence } from "./model";
import {
  createField,
  fieldTextInput,
  focusField,
  linkedChanges,
  newFieldId,
  paragraphIdentities,
  removeField,
  updateField,
} from "./transactions";
import "prosemirror-view/style/prosemirror.css";
import "./editor.css";
import type { components } from "../../generated/api";
import { attachReview, configureCandidate, focusCandidate, reviewCandidate, reviewChanges, reviewState, type ReviewState } from "./review";
import { ReviewPanel, type ReviewAction } from "./ReviewPanel";

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
  const view = useRef<EditorView | null>(null);
  const initial = useRef(initialDocument);
  const change = useRef(onDocumentChange);
  change.current = onDocumentChange;
  const [occurrences, setOccurrences] = useState<FieldOccurrence[]>([]);
  const [active, setActive] = useState("");
  const [label, setLabel] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [unsupported, setUnsupported] = useState(false);
  const [review, setReview] = useState<ReviewState | null>(null);
  const [reviewStale, setReviewStale] = useState(false);
  useEffect(() => {
    const editor = new EditorView(host.current!, {
      state: EditorState.create({
        schema: editorSchema,
        doc: editorSchema.nodeFromJSON(initial.current),
        plugins: [
          history(),
          keymap({ "Mod-z": undo, "Mod-Shift-z": redo, "Mod-y": redo }),
          keymap(baseKeymap),
        ],
      }),
      handleTextInput: fieldTextInput,
      dispatchTransaction(transaction: Transaction) {
        const next = editor.state.apply(
          reviewChanges(editor.state, paragraphIdentities(linkedChanges(editor.state, transaction))),
        );
        editor.updateState(next);
        if (transaction.docChanged && !transaction.getMeta("review-initial")) change.current?.(next.doc.toJSON());
        setReview(reviewState(next.doc));
        const nextFields = fields(next.doc);
        setOccurrences(nextFields);
        const selected = nextFields.find(
          (field) =>
            next.selection.from > field.pos &&
            next.selection.from < field.pos + field.size,
        );
        setActive(selected?.id ?? "");
      },
    });
    view.current = editor;
    setOccurrences(fields(editor.state.doc));
    setReview(reviewState(editor.state.doc));
    let locked = false;
    editor.state.doc.descendants((node) => {
      if (node.type.name.startsWith("locked")) locked = true;
    });
    setUnsupported(locked);
    return () => {
      editor.destroy();
      view.current = null;
    };
  }, []);
  useEffect(() => {
    view.current!.setProps({
      attributes: {
        "aria-label": t("editor.document"),
        role: "textbox",
        "aria-multiline": "true",
      },
    });
  }, [t]);

  useEffect(() => {
    const editor = view.current!;
    if (!discoverySnapshot || !sourceVersion || reviewState(editor.state.doc)) return;
    try {
      if (!editor.state.doc.content.eq(editorSchema.nodeFromJSON(initial.current).content)) throw new Error("changed_source");
      const attached = attachReview(editor.state.doc, discoverySnapshot, sourceVersion);
      editor.dispatch(editor.state.tr.setDocAttribute("review", reviewState(attached))
        .setMeta("review-initial", true).setMeta("addToHistory", false));
      setReviewStale(false);
    } catch { setReviewStale(true); }
  }, [discoverySnapshot, sourceVersion]);

  function actOnReview(id: string, action: ReviewAction, options: { label: string; key: string; type: string }): boolean {
    const editor = view.current!;
    const transaction = action === "focus" ? focusCandidate(editor.state, id)
      : action === "configure" ? configureCandidate(editor.state, id, options.label, options.key || newFieldId(), options.type)
      : reviewCandidate(editor.state, id, action, { ...options, key: options.key || undefined });
    if (!transaction) return false;
    editor.dispatch(transaction);
    if (action === "focus" || action === "accept") editor.focus();
    return true;
  }

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
          onClick={() => {
            const editor = view.current!;
            const transaction = createField(editor.state, label, newFieldId());
            setInvalid(!transaction);
            if (transaction) {
              editor.dispatch(transaction);
              editor.focus();
            }
          }}
        >
          {t("editor.createField")}
        </button>
        <button
          onClick={() => {
            const editor = view.current!;
            undo(editor.state, editor.dispatch);
            editor.focus();
          }}
        >
          {t("editor.undo")}
        </button>
        <button
          onClick={() => {
            const editor = view.current!;
            redo(editor.state, editor.dispatch);
            editor.focus();
          }}
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
          <ReviewPanel review={review} occurrences={occurrences} act={actOnReview} />
        </details>}
        {occurrences.map((field) => (
          <div key={field.id} data-active={active === field.id}>
            <label>
              {field.label}
              <input
                aria-label={t("editor.fieldValue", { label: field.label })}
                value={field.value}
                onChange={(event) =>
                  view.current!.dispatch(
                    updateField(
                      view.current!.state,
                      field.key,
                      event.target.value,
                    ),
                  )
                }
              />
            </label>
            <button
              onClick={() => {
                const editor = view.current!;
                const transaction = focusField(editor.state, field.id);
                if (transaction) {
                  editor.dispatch(transaction);
                  editor.focus();
                }
              }}
            >
              {t("editor.focus", { label: field.label })}
            </button>
            <button
              onClick={() => {
                const editor = view.current!;
                const transaction = removeField(editor.state, field.id);
                if (transaction) editor.dispatch(transaction);
              }}
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
