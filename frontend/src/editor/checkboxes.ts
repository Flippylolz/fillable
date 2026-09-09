import { NodeSelection, type Command, type EditorState } from "prosemirror-state";

export type CheckboxIssue = "select_box" | "read_only";

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
export function toggleGlyphCheckbox(state: EditorState) {
  const box = target(state);
  if (!box) return { issue: "select_box" as const };
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

/** Drawn form rectangles use white for cleared; dark authored fills mark checked. */
export const DRAWN_UNCHECKED_FILL = "#ffffff";
export const DRAWN_CHECKED_FALLBACK = "#595959";

function lightness(fill: string): number | null {
  if (!/^#[0-9a-fA-F]{6}$/.test(fill)) return null;
  return (0.299 * parseInt(fill.slice(1, 3), 16) + 0.587 * parseInt(fill.slice(3, 5), 16) + 0.114 * parseInt(fill.slice(5, 7), 16)) / 255;
}

/** Whether a rendered shape fill reads as an unmarked box (white or cleared). */
export function isLightFill(fill: string): boolean {
  const value = lightness(fill);
  return value === null || value >= 0.6;
}

/**
 * The fill after toggling one drawn rectangle: a light box takes the dark fill
 * the form itself uses for checked boxes, a dark box returns to a cleared one.
 */
export function shapeToggleFill(rendered: string, siblingRendered: string[]): string {
  if (!isLightFill(rendered)) return DRAWN_UNCHECKED_FILL;
  const dark = siblingRendered.find(fill => !isLightFill(fill));
  return dark ?? DRAWN_CHECKED_FALLBACK;
}
