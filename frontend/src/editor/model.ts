import { Schema, type Node as EditorNode } from "prosemirror-model";

export const editorSchema = new Schema({
  nodes: {
    doc: { content: "section+", attrs: { review: { default: null } } },
    section: {
      content: "block+",
      attrs: { part: { default: null } },
      toDOM: (node) => ["section", { "data-part": node.attrs.part }, 0],
      parseDOM: [
        {
          tag: "section[data-part]",
          getAttrs: (el) => ({ part: el.getAttribute("data-part") }),
        },
      ],
    },
    paragraph: {
      group: "block",
      content: "inline*",
      whitespace: "pre",
      attrs: {
        id: { default: null },
        align: { default: "left" },
        numbered: { default: false },
      },
      toDOM: (node) => [
        "p",
        {
          "data-source": node.attrs.id,
          "data-numbered": node.attrs.numbered,
          "data-align": node.attrs.align,
          style: `text-align:${node.attrs.align === "both" ? "justify" : node.attrs.align}`,
        },
        0,
      ],
      parseDOM: [
        {
          tag: "p",
          getAttrs: (el) => ({
            id: el.getAttribute("data-source"),
            align: el.getAttribute("data-align"),
            numbered: el.getAttribute("data-numbered") === "true",
          }),
        },
      ],
    },
    table: {
      group: "block",
      content: "tableRow+",
      attrs: { id: { default: null } },
      toDOM: (node) => [
        "table",
        { "data-source": node.attrs.id },
        ["tbody", 0],
      ],
      parseDOM: [
        {
          tag: "table",
          getAttrs: (el) => ({ id: el.getAttribute("data-source") }),
        },
      ],
    },
    tableRow: {
      content: "tableCell+",
      attrs: { id: { default: null } },
      toDOM: (node) => ["tr", { "data-source": node.attrs.id }, 0],
      parseDOM: [
        {
          tag: "tr",
          getAttrs: (el) => ({ id: el.getAttribute("data-source") }),
        },
      ],
    },
    tableCell: {
      group: "cell",
      content: "block+",
      attrs: { id: { default: null }, colspan: { default: 1 } },
      isolating: true,
      toDOM: (node) => [
        "td",
        { colspan: node.attrs.colspan, "data-source": node.attrs.id },
        0,
      ],
      parseDOM: [
        {
          tag: "td",
          getAttrs: (el) => ({
            id: el.getAttribute("data-source"),
            colspan: (el as HTMLTableCellElement).colSpan,
          }),
        },
      ],
    },
    field: {
      group: "inline",
      inline: true,
      content: "text*",
      whitespace: "pre",
      isolating: true,
      attrs: { id: { default: null }, key: {}, label: {} },
      toDOM: (node) => [
        "span",
        {
          class: "document-field",
          "data-field-id": node.attrs.id,
          "data-field-key": node.attrs.key,
          "data-field-label": node.attrs.label,
        },
        0,
      ],
      parseDOM: [
        {
          tag: "span[data-field-id]",
          getAttrs: (element) => ({
            id: element.getAttribute("data-field-id"),
            key: element.getAttribute("data-field-key"),
            label: element.getAttribute("data-field-label"),
          }),
        },
      ],
    },
    lockedInline: {
      group: "inline",
      inline: true,
      atom: true,
      attrs: { id: { default: null }, label: {} },
      toDOM: (node) => [
        "span",
        {
          contenteditable: "false",
          class: "document-unsupported",
          "data-locked": node.attrs.id,
        },
        node.attrs.label,
      ],
      parseDOM: [
        {
          tag: "span[data-locked]",
          getAttrs: (el) => ({
            id: el.getAttribute("data-locked"),
            label: el.textContent,
          }),
        },
      ],
    },
    lockedBlock: {
      group: "block",
      atom: true,
      attrs: { id: { default: null }, label: {} },
      toDOM: (node) => [
        "div",
        {
          contenteditable: "false",
          class: "document-unsupported",
          "data-locked": node.attrs.id,
        },
        node.attrs.label,
      ],
      parseDOM: [
        {
          tag: "div[data-locked]",
          getAttrs: (el) => ({
            id: el.getAttribute("data-locked"),
            label: el.textContent,
          }),
        },
      ],
    },
    text: { group: "inline" },
  },
  marks: {
    source: {
      attrs: {
        id: { default: null },
        bold: { default: false },
        italic: { default: false },
        underline: { default: false },
      },
      toDOM: (mark) => [
        "span",
        {
          "data-source-run": mark.attrs.id,
          "data-bold": mark.attrs.bold,
          "data-italic": mark.attrs.italic,
          "data-underline": mark.attrs.underline,
          style: `font-weight:${mark.attrs.bold ? "bold" : "normal"};font-style:${mark.attrs.italic ? "italic" : "normal"};text-decoration:${mark.attrs.underline ? "underline" : "none"}`,
        },
        0,
      ],
      parseDOM: [
        {
          tag: "span[data-source-run]",
          getAttrs: (el) => ({
            id: el.getAttribute("data-source-run"),
            bold: el.getAttribute("data-bold") === "true",
            italic: el.getAttribute("data-italic") === "true",
            underline: el.getAttribute("data-underline") === "true",
          }),
        },
      ],
    },
  },
});

export interface FieldOccurrence {
  id: string;
  key: string;
  label: string;
  value: string;
  pos: number;
  size: number;
}
export function fields(doc: EditorNode): FieldOccurrence[] {
  const result: FieldOccurrence[] = [];
  doc.descendants((node, pos) => {
    if (node.type.name === "field")
      result.push({
        id: node.attrs.id,
        key: node.attrs.key,
        label: node.attrs.label,
        value: node.textContent,
        pos,
        size: node.nodeSize,
      });
  });
  return result;
}
