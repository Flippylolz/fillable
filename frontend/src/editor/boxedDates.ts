import type { Node } from "prosemirror-model";
import type { EditorState } from "prosemirror-state";

type Slot = { from: number; to: number; digits: number };
export type DateBoxIssue = "invalid_date" | "select_boxes" | "read_only";

/** Real calendar dates only, including leap-year February. */
export function calendarValid(year: number, month: number, day: number): boolean {
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1];
}

function digitsFor(iso: string, count: number): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const [year, month, day] = iso.split("-").map(Number);
  if (!calendarValid(year, month, day)) return null;
  return iso.slice(8) + iso.slice(5, 7) + iso.slice(count === 6 ? 2 : 0, 4);
}

function plain(node: Node) {
  let valid = true;
  node.descendants(child => { if (!child.isText) valid = false; });
  return valid;
}

/** Source positions, never screen coordinates; all replacements share one undo step. */
export function fillBoxedDate(state: EditorState, iso: string) {
  const { from, to, $from, $to } = state.selection;
  let slots: Slot[] = [];
  if ($from.sameParent($to) && $from.parent.type.name === "paragraph" && plain($from.parent)) {
    const selected = state.doc.textBetween(from, to);
    // Separators remain untouched, including source run boundaries and spacing.
    if (/^\s*[\d_]\s*(?:[│|]\s*[\d_]\s*){5}(?:(?:[│|]\s*[\d_]\s*){2})?$/.test(selected)) {
      slots = [...selected.matchAll(/[\d_]/g)].map(match => ({ from: from + match.index!, to: from + match.index! + 1, digits: 1 }));
    }
  }
  if (!slots.length && from !== to) {
    let depth = $from.depth, endDepth = $to.depth;
    while (depth && $from.node(depth).type.name !== "tableRow") depth--;
    while (endDepth && $to.node(endDepth).type.name !== "tableRow") endDepth--;
    const row = depth && endDepth && $from.node(depth) === $to.node(endDepth) ? $from.node(depth) : null;
    let invalid = false;
    row?.forEach((node, offset) => {
      const pos = $from.start(depth) + offset;
      if (pos >= to || pos + node.nodeSize <= from) return;
      const paragraph = node.firstChild;
      const value = paragraph?.textContent.trim() ?? "";
      if (node.childCount !== 1 || paragraph?.type.name !== "paragraph" || !plain(paragraph) || !/^[\d_]{0,4}$/.test(value)) { invalid = true; return; }
      slots.push({ from: pos + 2, to: pos + 2 + paragraph.content.size, digits: value.length || 1 });
    });
    if (invalid || !row || ![6, 8].includes(slots.length) && !(slots.length === 3 && slots[0].digits === 2 && slots[1].digits === 2 && [2, 4].includes(slots[2].digits))) slots = [];
    if ([6, 8].includes(slots.length) && slots.some(slot => slot.digits !== 1)) slots = [];
  }
  const count = slots.reduce((sum, slot) => sum + slot.digits, 0);
  if (![6, 8].includes(count)) return { issue: "select_boxes" as const };
  const digits = digitsFor(iso, count);
  if (!digits) return { issue: "invalid_date" as const };
  const transaction = state.tr;
  let offset = count;
  for (const slot of [...slots].reverse()) {
    offset -= slot.digits;
    const marks = state.doc.resolve(slot.from).marks();
    transaction.replaceWith(slot.from, slot.to, state.schema.text(digits.slice(offset, offset + slot.digits), marks));
  }
  return { transaction };
}
