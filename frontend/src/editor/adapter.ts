import { fillBoxedDate, type DateBoxIssue } from "./boxedDates";
import { glyphCheckboxReady, shapeToggleFill, toggleGlyphCheckbox, toggleSelectedCheckbox, type CheckboxIssue } from "./checkboxes";
import { sourceNodeView } from "./sourceNodes";
import type { SourcePresentation } from "./SourceLayout";
import { EditorState, Plugin, PluginKey, type Transaction } from "prosemirror-state";
import { Decoration, DecorationSet, EditorView } from "prosemirror-view";
import { history, undo, redo, closeHistory } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import { baseKeymap } from "prosemirror-commands";
import type { components } from "../../generated/api";
import { editorSchema, fields, type FieldOccurrence } from "./model";
import { suggestFieldLabel } from "./transactions";
import { collapseFieldSelection, createField, fieldBeforeInput, fieldLineBreak, fieldPaste, fieldTextInput, focusField, linkedChanges, manualFieldIssue, newFieldId, paragraphIdentities, removeField, retainComposedField, updateField } from "./transactions";
import { attachReview, configureCandidate, focusCandidate, reviewCandidate, reviewChanges, reviewState, type ReviewState } from "./review";
import { fieldValueIssue, type FieldValueIssue } from "./fieldValues";
import { isFieldType, type FieldType } from "./fieldKinds";
import { pageBreakPlugin } from "./pagination";

export type FieldSummary = Pick<FieldOccurrence, "id" | "key" | "label" | "value"> & { type: FieldType; issue: FieldValueIssue };
export type ReviewAction = "accept" | "dismiss" | "configure" | "focus";
export type ReviewOptions = { label: string; key: string; type: string };
export type EditorPresentation = { fields: FieldSummary[]; active: string; review: ReviewState | null; unsupported: boolean; fieldValuesValid: boolean; composing: boolean; glyphCheckbox: boolean; canUndo: boolean; canRedo: boolean; suggestLabel: string };
export type EditorSnapshot = { document: object; revision: number; fieldValuesValid: boolean; composing: boolean };

const retainedSelectionKey = new PluginKey<{ range: { from: number; to: number } | null }>("retain-selection");
type RetainedRange = { range: { from: number; to: number } | null };

/** Keeps the chosen document range highlighted while the naming input holds focus. */
function retainedSelectionPlugin() {
  return new Plugin<RetainedRange>({
    key: retainedSelectionKey,
    state: {
      init: () => ({ range: null }),
      apply(tr, previous) {
        if (tr.getMeta("retain-selection") !== undefined) return { range: tr.getMeta("retain-selection") };
        if (tr.selectionSet || !previous.range) return { range: null };
        return { range: { from: tr.mapping.map(previous.range.from), to: tr.mapping.map(previous.range.to) } };
      },
    },
    props: {
      decorations(state: EditorState): DecorationSet | undefined {
        const range = retainedSelectionKey.getState(state)?.range;
        if (!range || range.to <= range.from) return undefined;
        return DecorationSet.create(state.doc, [Decoration.inline(range.from, range.to, { class: "document-selection-retained" })]);
      },
    },
  });
}

/** The mounted editor owns document state. Callers receive detached snapshots only. */
export function mountEditor(host: HTMLElement, initialDocument: object, callbacks: {
  presentation?: SourcePresentation;
  canEdit?: () => boolean;
  onChange: (snapshot: EditorSnapshot) => void;
  onUpdate: (presentation: EditorPresentation) => void;
}) {
  const source = editorSchema.nodeFromJSON(structuredClone(initialDocument));
  let revision = 0, unsupported = false, settling = false;
  let pageBreakLabel: ((page: number) => string) | null = null;
  let shapeCheckboxLabel = "";
  const pageBreaks: { refresh: (force?: boolean) => void } = { refresh: () => {} };
  const historyPlugin = history();
  const allowed = () => callbacks.canEdit?.() !== false;
  let compositionSource: EditorState | null = null;
  let compositionChanges: Transaction | null = null;
  let compositionId: number | undefined;
  let compositionTimer: ReturnType<typeof setTimeout> | undefined;
  source.descendants(node => { if (node.type.name.startsWith("locked")) unsupported = true; });
  const editor = new EditorView(host, {
    nodeViews: {
      lockedInline: sourceNodeView(callbacks.presentation, () => shapeCheckboxLabel),
      lockedBlock: sourceNodeView(callbacks.presentation, () => shapeCheckboxLabel),
    },
    editable: () => allowed() || compositionSource !== null,
    state: EditorState.create({ schema: editorSchema, doc: source,
      plugins: [historyPlugin, retainedSelectionPlugin(), pageBreakPlugin(() => pageBreakLabel ?? (page => String(page)), pageBreaks), keymap({ "Mod-z": undo, "Mod-Shift-z": redo, "Mod-y": redo, Enter: fieldLineBreak, "Shift-Enter": fieldLineBreak,
        " ": toggleSelectedCheckbox, ArrowRight: collapseFieldSelection(true), ArrowLeft: collapseFieldSelection(false) }), keymap(baseKeymap)],
    }),
    handleTextInput: (view, from, to, value) => !allowed() && !compositionSource || fieldTextInput(view, from, to, value),
    handleDOMEvents: {
      beforeinput(view, event) {
        if (!allowed() && !compositionSource) { event.preventDefault(); return true; }
        return fieldBeforeInput(view, event);
      },
      click(view, event) {
        // Leaf checkbox controls are uneditable DOM; route direct clicks to a toggle.
        const target = event.target as HTMLElement | null;
        const box = target?.closest?.("span.document-checkbox");
        if (box && view.dom.contains(box)) {
          const position = view.posAtDOM(box, 0);
          const node = view.state.doc.nodeAt(position);
          if (!node || node.type.name !== "checkbox" || !allowed() || compositionSource) return false;
          editor.dispatch(closeHistory(editor.state.tr.setNodeMarkup(position, undefined, { ...node.attrs, checked: !node.attrs.checked })));
          event.preventDefault();
          return true;
        }
        return toggleShape(target, event as MouseEvent);
      },
      compositionstart(_view, event) {
        if (!allowed()) { event.preventDefault(); return true; }
        finishComposition();
        compositionSource = editor.state;
        compositionChanges = editor.state.tr;
        compositionId = undefined;
        publish();
        return false;
      },
      compositionend() {
        // The pinned view settles composition/queued DOM mutations after 20 ms.
        // Synchronize only after that flush, including unchanged final candidates.
        compositionTimer = setTimeout(finishComposition, 25);
        return false;
      },
    },
    handlePaste: (view, event) => !allowed() || fieldPaste(view, event),
    dispatchTransaction(transaction: Transaction) {
      if (transaction.docChanged && !transaction.getMeta("review-initial") && !allowed() && !compositionSource && !settling) { editor.updateState(editor.state); return; }
      if (compositionSource && typeof transaction.getMeta("composition") === "number") compositionId = transaction.getMeta("composition");
      const transformed = paragraphIdentities(compositionSource ? transaction : linkedChanges(editor.state, transaction));
      if (compositionChanges) for (const step of transformed.steps) compositionChanges.step(step);
      const next = editor.state.apply(compositionSource ? transformed : reviewChanges(editor.state, transformed));
      editor.updateState(next);
      if (transaction.docChanged && !transaction.getMeta("review-initial")) {
        revision += 1;
        callbacks.onChange(exportSnapshot());
      }
      publish();
    },
  });
  function toggleShape(target: HTMLElement | null, event: MouseEvent): boolean {
    // Drawn form rectangles toggle like checkboxes: one bounded fill change.
    const shape = target?.closest?.<HTMLElement>("span.document-shape");
    if (!shape || !editor.dom.contains(shape) || !allowed() || compositionSource) return false;
    const holder = shape.closest<HTMLElement>("[data-locked]");
    if (!holder || !editor.dom.contains(holder)) return false;
    const position = editor.posAtDOM(holder, 0);
    const node = editor.state.doc.nodeAt(position);
    if (!node || node.type.name !== "lockedInline") return false;
    const boxes = Array.from(holder.querySelectorAll<HTMLElement>("span.document-shape"));
    const index = boxes.indexOf(shape);
    if (index < 0) return false;
    const fills = boxes.map(element => element.dataset.fill ?? "");
    const overrides = { ...(node.attrs.shapes as Record<string, string>), [String(index)]: shapeToggleFill(fills[index], fills) };
    editor.dispatch(closeHistory(editor.state.tr.setNodeMarkup(position, undefined, { ...node.attrs, shapes: overrides })));
    event.preventDefault();
    return true;
  }
  function finishComposition() {
    clearTimeout(compositionTimer);
    const source = compositionSource;
    const changes = compositionChanges;
    compositionSource = null;
    compositionChanges = null;
    if (!source) return;
    if (source.doc.eq(editor.state.doc)) { editor.setProps({}); publish(); return; }
    const transaction = linkedChanges(source, retainComposedField(source, editor.state.tr, changes!.mapping), true);
    for (const step of transaction.steps) changes!.step(step);
    const review = reviewState(reviewChanges(source, changes!).doc);
    if (review !== reviewState(editor.state.doc)) transaction.setDocAttribute("review", review);
    if (transaction.docChanged) {
      if (compositionId !== undefined) transaction.setMeta("composition", compositionId);
      settling = true;
      try { editor.dispatch(transaction); } finally { settling = false; }
    } else publish();
    editor.setProps({});
  }
  function exportSnapshot(): EditorSnapshot {
    const types = occurrenceTypes();
    return { document: structuredClone(editor.state.doc.toJSON()), revision, composing: compositionSource !== null,
      fieldValuesValid: fields(editor.state.doc).every(field => fieldValueIssue(field.value, types.get(field.id)) === null) };
  }
  // The review record owns each field's type; occurrences without one are text.
  // Accepted controls map by live control identity, not the discovery occurrence.
  function occurrenceTypes(): Map<string, FieldType> {
    const result = new Map<string, FieldType>();
    for (const item of reviewState(editor.state.doc)?.items ?? []) {
      if (!isFieldType(item.type)) continue;
      result.set(item.location.kind === "control" ? item.location.id : item.occurrenceId, item.type);
    }
    return result;
  }
  function publish() {
    const occurrences = fields(editor.state.doc);
    const types = occurrenceTypes();
    const active = occurrences.find(field => editor.state.selection.from > field.pos && editor.state.selection.from < field.pos + field.size)?.id ?? "";
    const summaries = occurrences.map(({ id, key, label, value }) => ({ id, key, label, value,
      type: types.get(id) ?? "text", issue: fieldValueIssue(value, types.get(id)) }));
    const history = historyPlugin.getState(editor.state);
    callbacks.onUpdate({ fields: summaries, fieldValuesValid: summaries.every(field => field.issue === null),
      active, review: structuredClone(reviewState(editor.state.doc)), unsupported, composing: compositionSource !== null,
      glyphCheckbox: allowed() && glyphCheckboxReady(editor.state),
      canUndo: (history?.done.eventCount ?? 0) > 0, canRedo: (history?.undone.eventCount ?? 0) > 0,
      suggestLabel: suggestFieldLabel(editor.state) });
  }
  function dispatch(transaction: Transaction | null, focus = false): boolean {
    if (!transaction || (transaction.docChanged && !allowed())) return false;
    editor.dispatch(transaction);
    if (focus) editor.focus();
    return true;
  }
  publish();
  return {
    exportSnapshot,
    refreshAccess() { editor.setProps({}); },
    setDocumentLabel(label: string) {
      editor.setProps({ attributes: () => ({ "aria-label": label, role: "textbox", "aria-multiline": "true", "aria-readonly": String(!allowed()) }) });
    },
    setPageBreakLabel(formatter: (page: number) => string) {
      pageBreakLabel = formatter;
      pageBreaks.refresh(true);
    },
    setShapeCheckboxLabel(label: string) {
      shapeCheckboxLabel = label;
      for (const element of editor.dom.querySelectorAll<HTMLElement>("span.document-shape"))
        element.setAttribute("aria-label", label);
    },
    retainSelection(retain: boolean) {
      const { from, to, empty } = editor.state.selection;
      const range = retain && !empty && to > from ? { from, to } : null;
      editor.dispatch(editor.state.tr.setMeta("retain-selection", range).setMeta("addToHistory", false));
    },
    attachDiscovery(snapshot: components["schemas"]["FieldSnapshot"], sourceVersion: string, reviewSaved = false): boolean {
      if (compositionSource) return false;
      const current = reviewState(editor.state.doc);
      if (current) return current.sourceVersion !== null || reviewSaved;
      try {
        if (!editor.state.doc.content.eq(source.content)) return false;
        const attached = attachReview(editor.state.doc, snapshot, sourceVersion);
        editor.dispatch(editor.state.tr.setDocAttribute("review", reviewState(attached))
          .setMeta("review-initial", true).setMeta("addToHistory", false));
        return true;
      } catch { return false; }
    },
    review(id: string, action: ReviewAction, options: ReviewOptions): boolean {
      const transaction = action === "focus" ? focusCandidate(editor.state, id)
        : action === "configure" ? configureCandidate(editor.state, id, options.label, options.key || newFieldId(), options.type)
        : reviewCandidate(editor.state, id, action, { ...options, key: options.key || undefined });
      return dispatch(transaction, action === "focus" || action === "accept");
    },
    fillDate(iso: string): DateBoxIssue | null {
      if (!allowed() || compositionSource) return "read_only";
      const result = fillBoxedDate(editor.state, iso);
      if (result.issue) return result.issue;
      dispatch(closeHistory(result.transaction!), true);
      return null;
    },
    toggleGlyph(): CheckboxIssue | null {
      if (!allowed() || compositionSource) return "read_only";
      const result = toggleGlyphCheckbox(editor.state);
      if (result.issue) return result.issue;
      dispatch(closeHistory(result.transaction!), true);
      return null;
    },
    createField(label: string) {
      if (!allowed()) return "read_only" as const;
      const issue = manualFieldIssue(editor.state, label);
      if (!issue) dispatch(createField(editor.state, label, newFieldId()), true);
      return issue;
    },
    updateField(key: string, value: string) {
      const transaction = updateField(editor.state, key, value);
      return transaction.docChanged && dispatch(transaction);
    },
    focusField(id: string) { return dispatch(focusField(editor.state, id), true); },
    removeField(id: string) { return dispatch(removeField(editor.state, id)); },
    undo() { if (!allowed()) return false; const changed = undo(editor.state, editor.dispatch); editor.focus(); return changed; },
    redo() { if (!allowed()) return false; const changed = redo(editor.state, editor.dispatch); editor.focus(); return changed; },
    destroy() { clearTimeout(compositionTimer); editor.destroy(); },
  };
}

export type EditorAdapter = ReturnType<typeof mountEditor>;
