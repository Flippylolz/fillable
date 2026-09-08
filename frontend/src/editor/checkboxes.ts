import type { Command } from "prosemirror-state";
import { NodeSelection, type EditorState, type Transaction } from "prosemirror-state";

export type CheckboxIssue = "select_box" | "read_only";
export type CheckboxOutcome = { issue: CheckboxIssue } | { transaction: Transaction };

/** Unambiguous ballot-box pairs; symbol-font private-use codes stay out of scope. */
const PAIRS: Record<string, string> = { "\u2610": "\u2612", "\u2612": "\u2610" };

export function glyphSwap(character: string): string | null {
  return PAIRS[character] ?? null;
}

function target(state: EditorState): { from: number; to: number; glyph: string } | null {
  const { from, to, $from, $to } = state.selection;
  if (to !== from + 1 || !$from.sameParent($to) || $from.parent.type.name !== "paragraph") return null;
  const glyph = state.doc.textBetween(from, to);
  return glyphSwap(glyph) ? { from, to, glyph } : null;
}

/** One selected ballot-box character swaps to its pair, preserving formatting. */
export function toggleGlyphCheckbox(state: EditorState): CheckboxOutcome {
  const box = target(state);
  if (!box) return { issue: "select_box" };
  const marks = state.doc.resolve(box.from).marks();
  return {
    transaction: state.tr.replaceWith(
      box.from,
      box.to,
      state.schema.text(glyphSwap(box.glyph)!, marks),
    ),
  };
}

/** Whether the current selection holds one togglable ballot-box character. */
export function glyphCheckboxReady(state: EditorState): boolean {
  return target(state) !== null;
}

/** Space/Enter on a selected checkbox control flips its state in one undo step. */
export const toggleSelectedCheckbox: Command = (state, dispatch) => {
  if (!(state.selection instanceof NodeSelection)) return false;
  const node = state.selection.node;
  if (node.type.name !== "checkbox") return false;
  dispatch?.(state.tr.setNodeMarkup(state.selection.from, undefined, { ...node.attrs, checked: !node.attrs.checked }));
  return true;
};
