import { Node, mergeAttributes } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Image from "@tiptap/extension-image";
import Placeholder from "@tiptap/extension-placeholder";
import { TableKit } from "@tiptap/extension-table";

const PageBreak = Node.create({
  name: "pageBreak",
  group: "block",
  atom: true,
  selectable: true,

  parseHTML() {
    return [{ tag: 'hr[data-pagebreak="true"]' }];
  },

  renderHTML() {
    return ["hr", { "data-pagebreak": "true", class: "editor-pagebreak" }];
  },
});

const ColumnBlock = Node.create({
  name: "columnBlock",
  content: "block+",
  isolating: true,

  parseHTML() {
    return [{ tag: "div[data-layout-column]" }];
  },

  renderHTML() {
    return ["div", { "data-layout-column": "true", class: "doc-column editor-column" }, 0];
  },
});

const ColumnsBlock = Node.create({
  name: "columnsBlock",
  group: "block",
  content: "columnBlock+",
  isolating: true,
  defining: true,

  addAttributes() {
    return {
      count: {
        default: 2,
        parseHTML: (element) => Number(element.getAttribute("data-count") || 2),
        renderHTML: (attributes) => ({ "data-count": String(attributes.count || 2) }),
      },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-layout="columns"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    const count = Number(HTMLAttributes["data-count"] || 2);
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-layout": "columns",
        class: `doc-columns editor-columns doc-columns-${count} editor-columns-${count}`,
      }),
      0,
    ];
  },
});

const AudioBlock = Node.create({
  name: "audioBlock",
  group: "block",
  atom: true,
  selectable: true,

  addAttributes() {
    return {
      src: {
        default: null,
      },
      dataAssetPath: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-asset-path"),
        renderHTML: (attributes) =>
          attributes.dataAssetPath ? { "data-asset-path": attributes.dataAssetPath } : {},
      },
    };
  },

  parseHTML() {
    return [{ tag: "audio[data-editor-audio]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["audio", mergeAttributes(HTMLAttributes, { controls: "controls", "data-editor-audio": "true" })];
  },
});

const WorksheetLink = Link.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      class: {
        default: "worksheet-link",
      },
      dataWorksheetSlug: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-worksheet-slug"),
        renderHTML: (attributes) =>
          attributes.dataWorksheetSlug ? { "data-worksheet-slug": attributes.dataWorksheetSlug } : {},
      },
    };
  },
});

const RichImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      class: {
        default: "doc-image doc-align-center doc-w-100",
      },
      dataAssetPath: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-asset-path"),
        renderHTML: (attributes) =>
          attributes.dataAssetPath ? { "data-asset-path": attributes.dataAssetPath } : {},
      },
    };
  },
});

export function editorExtensions() {
  return [StarterKit.configure({link:false, underline:false}), Placeholder.configure({placeholder:"Escribe aquí tu material."}), WorksheetLink.configure({openOnClick:false}), RichImage, AudioBlock, PageBreak, ColumnsBlock, ColumnBlock, TableKit.configure({table:{resizable:false}})];
}
