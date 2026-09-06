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
import { reviewChanges } from "./review";

export function DocumentEditor({
  initialDocument,
  onDocumentChange,
}: {
  initialDocument: object;
  onDocumentChange?: (document: object) => void;
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
        if (transaction.docChanged) change.current?.(next.doc.toJSON());
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
