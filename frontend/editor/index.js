import { Editor, Node, mergeAttributes } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Image from "@tiptap/extension-image";
import Placeholder from "@tiptap/extension-placeholder";
import { marked } from "marked";
import TurndownService from "turndown";

const PAGEBREAK_MARKER = "<!-- pagebreak -->";
const COLUMN_START_PATTERN = /^\s*\[\[columns:(2|3)\]\]\s*$/i;
const COLUMN_SEPARATOR_PATTERN = /^\s*\[\[col\]\]\s*$/i;
const COLUMN_END_PATTERN = /^\s*\[\[\/columns\]\]\s*$/i;
const WORKSHEET_TOKEN_PATTERN = /\[\[worksheet:([A-Za-z0-9\-_]+)(?:\|([^\]]+))?\]\]/gi;
const IMAGE_WITH_ATTR_PATTERN = /!\[([^\]]*)\]\(([^)]+)\)\{:\s*([^}]+)\s*\}/g;
const IMAGE_PATTERN = /!\[([^\]]*)\]\(([^)]+)\)/g;
const AUDIO_PATTERN = /<audio\s+controls\s+src="([^"]+)"\s*><\/audio>/gi;

marked.setOptions({
  gfm: true,
  breaks: false,
});

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
    const count = HTMLAttributes.count || 2;
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

function sanitizeAssetFilename(filename) {
  const lastDot = filename.lastIndexOf(".");
  const stem = lastDot === -1 ? filename : filename.slice(0, lastDot);
  const extension = lastDot === -1 ? "" : filename.slice(lastDot).toLowerCase();
  return `${slugifyName(stem) || "asset"}${extension}`;
}

function slugifyName(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function humanizeAssetName(filename) {
  return filename
    .replace(/\.[^.]+$/, "")
    .replace(/[-_]+/g, " ")
    .trim();
}

function formatBranchLabel(branchName = "") {
  if (!branchName) return "Sin seleccionar";
  if (branchName === "main") return "Material compartido";
  if (branchName.startsWith("users/")) {
    const friendlyName = branchName
      .slice("users/".length)
      .split("-")
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
    return `Espacio personal${friendlyName ? ` · ${friendlyName}` : ""}`;
  }
  return branchName;
}

function buildMediaClass(align = "center", size = "100") {
  return `doc-image doc-align-${align} doc-w-${size}`;
}

function parseMediaClass(value = "") {
  const align = value.match(/doc-align-(left|center|right)/)?.[1] || "center";
  const size = value.match(/doc-w-(100|66|50|33)/)?.[1] || "100";
  return { align, size };
}

function resolveAssetUrl(form, path) {
  if (!path || !path.startsWith("assets/")) return path;
  const bookId = form.querySelector("[data-editor-book-id]")?.value;
  const branchName = form.querySelector("[data-editor-branch]")?.value;
  if (!bookId || !branchName) return path;
  return `/books/${bookId}/${path}?branch=${branchName}`;
}

function convertMarkdownImages(chunk, form) {
  let prepared = chunk.replace(IMAGE_WITH_ATTR_PATTERN, (_match, alt, path, classes) => {
    const classValue = classes
      .split(/\s+/)
      .filter((item) => item.startsWith("."))
      .map((item) => item.slice(1))
      .join(" ");
    const cleanPath = path.trim();
    return `<img src="${resolveAssetUrl(form, cleanPath)}" alt="${alt}" class="${classValue}" data-asset-path="${cleanPath}" />`;
  });

  prepared = prepared.replace(IMAGE_PATTERN, (match, alt, path) => {
    if (match.includes("{:")) return match;
    const cleanPath = path.trim();
    return `<img src="${resolveAssetUrl(form, cleanPath)}" alt="${alt}" class="${buildMediaClass()}" data-asset-path="${cleanPath}" />`;
  });

  prepared = prepared.replace(AUDIO_PATTERN, (_match, path) => {
    const cleanPath = path.trim();
    return `<audio controls src="${resolveAssetUrl(form, cleanPath)}" data-editor-audio="true" data-asset-path="${cleanPath}"></audio>`;
  });

  return prepared;
}

function replaceWorksheetTokens(chunk) {
  return chunk.replace(WORKSHEET_TOKEN_PATTERN, (_match, slug, label) => {
    const finalLabel = (label || slug.replace(/-/g, " ")).trim();
    return `<a href="#worksheet-${slug}" class="worksheet-link" data-worksheet-slug="${slug}">${finalLabel}</a>`;
  });
}

function renderMarkdownChunk(chunk, form) {
  const prepared = replaceWorksheetTokens(convertMarkdownImages(chunk, form)).replaceAll(
    PAGEBREAK_MARKER,
    '<hr data-pagebreak="true" class="editor-pagebreak" />',
  );
  return marked.parse(prepared);
}

function markdownToEditorHtml(markdownText, form) {
  const lines = (markdownText || "").split("\n");
  const fragments = [];
  const buffer = [];
  let index = 0;

  const flushBuffer = () => {
    if (!buffer.length) return;
    const chunk = buffer.join("\n").trim();
    buffer.length = 0;
    if (chunk) fragments.push(renderMarkdownChunk(chunk, form));
  };

  while (index < lines.length) {
    const match = lines[index].match(COLUMN_START_PATTERN);
    if (!match) {
      buffer.push(lines[index]);
      index += 1;
      continue;
    }

    flushBuffer();
    const count = Number(match[1]);
    const columns = [];
    const current = [];
    index += 1;

    while (index < lines.length) {
      const currentLine = lines[index];
      if (COLUMN_SEPARATOR_PATTERN.test(currentLine)) {
        columns.push(current.join("\n").trim());
        current.length = 0;
        index += 1;
        continue;
      }
      if (COLUMN_END_PATTERN.test(currentLine)) {
        columns.push(current.join("\n").trim());
        index += 1;
        break;
      }
      current.push(currentLine);
      index += 1;
    }

    const columnHtml = columns
      .slice(0, count)
      .map((column) => {
        const content = column || "_Columna vacía_";
        return `<div data-layout-column="true" class="doc-column editor-column">${renderMarkdownChunk(content, form)}</div>`;
      })
      .join("");

    fragments.push(`<div data-layout="columns" data-count="${count}" class="doc-columns editor-columns doc-columns-${count} editor-columns-${count}">${columnHtml}</div>`);
  }

  flushBuffer();
  return fragments.join("\n");
}

function buildTurndown() {
  const service = new TurndownService({
    bulletListMarker: "-",
    headingStyle: "atx",
    codeBlockStyle: "fenced",
  });

  service.keep(["audio"]);

  service.addRule("pageBreak", {
    filter: (node) => node.nodeName === "HR" && node.getAttribute("data-pagebreak") === "true",
    replacement: () => `\n\n${PAGEBREAK_MARKER}\n\n`,
  });

  service.addRule("worksheetLink", {
    filter: (node) => node.nodeName === "A" && node.getAttribute("data-worksheet-slug"),
    replacement: (_content, node) => {
      const slug = node.getAttribute("data-worksheet-slug");
      const label = (node.textContent || slug || "").trim();
      return `[[worksheet:${slug}|${label}]]`;
    },
  });

  service.addRule("richImage", {
    filter: (node) => node.nodeName === "IMG" && node.getAttribute("data-asset-path"),
    replacement: (_content, node) => {
      const path = node.getAttribute("data-asset-path") || node.getAttribute("src") || "";
      const alt = node.getAttribute("alt") || "";
      const classValue = node.getAttribute("class") || buildMediaClass();
      const classes = classValue
        .split(/\s+/)
        .filter((value) => value && value !== "ProseMirror-selectednode")
        .map((value) => `.${value}`)
        .join(" ");
      return `![${alt}](${path}){: ${classes}}`;
    },
  });

  service.addRule("audioBlock", {
    filter: (node) => node.nodeName === "AUDIO" && (node.getAttribute("data-asset-path") || node.getAttribute("src")),
    replacement: (_content, node) => {
      const path = node.getAttribute("data-asset-path") || node.getAttribute("src") || "";
      return `<audio controls src="${path}"></audio>`;
    },
  });

  service.addRule("columnsBlock", {
    filter: (node) => node.nodeName === "DIV" && node.getAttribute("data-layout") === "columns",
    replacement: (_content, node) => {
      const count = Number(node.getAttribute("data-count") || 2);
      const columns = [...node.querySelectorAll(':scope > div[data-layout-column]')].map((column) => {
        const converted = service.turndown(column.innerHTML).trim();
        return converted || "Escribe aquí el contenido de la columna.";
      });
      return `\n\n[[columns:${count}]]\n${columns.join("\n[[col]]\n")}\n[[/columns]]\n\n`;
    },
  });

  return service;
}

function serializeTextWithMarks(node) {
  let value = node.text || "";
  const marks = [...(node.marks || [])];
  const order = { bold: 1, italic: 2, link: 3 };
  marks.sort((left, right) => (order[left.type] || 99) - (order[right.type] || 99));

  marks.forEach((mark) => {
    if (mark.type === "bold") value = `**${value}**`;
    if (mark.type === "italic") value = `*${value}*`;
    if (mark.type === "link") {
      const attrs = mark.attrs || {};
      if (attrs.dataWorksheetSlug) {
        value = `[[worksheet:${attrs.dataWorksheetSlug}|${value}]]`;
      } else if (attrs.href) {
        value = `[${value}](${attrs.href})`;
      }
    }
  });

  return value;
}

function serializeInlineNodes(nodes = []) {
  return nodes
    .map((node) => {
      if (node.type === "text") return serializeTextWithMarks(node);
      if (node.type === "hardBreak") return "  \n";
      return serializeNode(node);
    })
    .join("");
}

function indentMarkdown(markdown, prefix = "  ") {
  return markdown
    .split("\n")
    .map((line) => (line ? `${prefix}${line}` : line))
    .join("\n");
}

function serializeListItem(node, prefix) {
  const blocks = (node.content || []).map((child) => serializeNode(child)).filter(Boolean);
  if (!blocks.length) return prefix.trimEnd();

  const firstLines = blocks[0].split("\n");
  const lines = [`${prefix}${firstLines[0]}`];
  firstLines.slice(1).forEach((line) => lines.push(line ? `  ${line}` : ""));

  blocks.slice(1).forEach((block) => {
    block.split("\n").forEach((line) => lines.push(line ? `  ${line}` : ""));
  });

  return lines.join("\n");
}

function serializeList(node, ordered = false) {
  return (node.content || [])
    .map((item, index) => serializeListItem(item, ordered ? `${index + 1}. ` : "- "))
    .join("\n");
}

function serializeColumns(node) {
  const count = Number(node.attrs?.count || (node.content || []).length || 2);
  const columns = (node.content || []).map((column) => {
    const content = serializeBlocks(column.content || []);
    return content || "_Columna vacia_";
  });
  return `[[columns:${count}]]\n${columns.join("\n[[col]]\n")}\n[[/columns]]`;
}

function serializeImage(node) {
  const attrs = node.attrs || {};
  const path = attrs.dataAssetPath || attrs.src || "";
  const alt = attrs.alt || "";
  const classValue = attrs.class || buildMediaClass();
  const classes = classValue
    .split(/\s+/)
    .filter((value) => value && value !== "ProseMirror-selectednode")
    .map((value) => `.${value}`)
    .join(" ");
  return `![${alt}](${path}){: ${classes}}`;
}

function serializeAudio(node) {
  const attrs = node.attrs || {};
  const path = attrs.dataAssetPath || attrs.src || "";
  return `<audio controls src="${path}"></audio>`;
}

function serializeNode(node) {
  if (!node) return "";
  if (node.type === "text") return serializeTextWithMarks(node);
  if (node.type === "paragraph") return serializeInlineNodes(node.content || []).trim();
  if (node.type === "heading") return `${"#".repeat(node.attrs?.level || 2)} ${serializeInlineNodes(node.content || []).trim()}`.trim();
  if (node.type === "bulletList") return serializeList(node, false);
  if (node.type === "orderedList") return serializeList(node, true);
  if (node.type === "blockquote") {
    return serializeBlocks(node.content || [])
      .split("\n")
      .map((line) => (line ? `> ${line}` : ">"))
      .join("\n");
  }
  if (node.type === "pageBreak") return PAGEBREAK_MARKER;
  if (node.type === "columnsBlock") return serializeColumns(node);
  if (node.type === "columnBlock") return serializeBlocks(node.content || []);
  if (node.type === "image") return serializeImage(node);
  if (node.type === "audioBlock") return serializeAudio(node);
  if (node.type === "horizontalRule") return "---";
  return serializeInlineNodes(node.content || []).trim();
}

function serializeBlocks(nodes = []) {
  return nodes
    .map((node) => serializeNode(node))
    .filter((value) => value && value.trim())
    .join("\n\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function serializeEditorDocument(editor) {
  const documentJson = editor.getJSON();
  return serializeBlocks(documentJson.content || []);
}

function buildPendingAssetSummary(files) {
  return files.length ? files.map((file) => sanitizeAssetFilename(file.name)).join(", ") : "Sin archivos nuevos en esta sesión.";
}

function extractAssetFilename(url) {
  try {
    return sanitizeAssetFilename(new URL(url, window.location.origin).pathname.split("/").pop() || "");
  } catch (_error) {
    return sanitizeAssetFilename((url || "").split("?")[0].split("/").pop() || "");
  }
}

function hydrateDraftAssetsInPreview(form) {
  const preview = form.querySelector("[data-rich-preview]");
  if (!preview) return;
  const pendingFiles = [...form._richState.transfer.files];
  if (!pendingFiles.length) return;
  const pendingMap = new Map(
    pendingFiles.map((file) => [sanitizeAssetFilename(file.name), createObjectUrl(file, form._richState)]),
  );

  preview.querySelectorAll("img[src], audio[src]").forEach((element) => {
    const filename = extractAssetFilename(element.getAttribute("src") || "");
    const objectUrl = pendingMap.get(filename);
    if (objectUrl) element.setAttribute("src", objectUrl);
  });
}

function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function initializeBookDocuments(root = document) {
  root.querySelectorAll("[data-book-document]").forEach((container) => {
    if (container.dataset.documentReady === "true") return;
    container.dataset.documentReady = "true";
    const pages = [...container.querySelectorAll("[data-book-page]")];
    if (!pages.length) return;

    const setActivePage = (nextPageNumber, anchorId = null) => {
      const boundedPageNumber = Math.min(Math.max(nextPageNumber, 1), pages.length);
      pages.forEach((page) => {
        const isActive = Number(page.dataset.pageNumber) === boundedPageNumber;
        page.classList.toggle("is-active", isActive);
      });
      const indicator = container.querySelector("[data-page-indicator]");
      if (indicator) indicator.textContent = `Pagina ${boundedPageNumber} de ${pages.length}`;
      const previous = container.querySelector("[data-page-prev]");
      const next = container.querySelector("[data-page-next]");
      if (previous) previous.disabled = boundedPageNumber === 1;
      if (next) next.disabled = boundedPageNumber === pages.length;
      container.querySelectorAll("[data-page-target]").forEach((item) => {
        item.classList.toggle("is-active", Number(item.dataset.pageTarget) === boundedPageNumber);
      });
      if (anchorId) container.querySelector(`#${anchorId}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
    };

    container.querySelector("[data-page-prev]")?.addEventListener("click", () => {
      const current = Number(container.querySelector(".document-page.is-active")?.dataset.pageNumber || 1);
      setActivePage(current - 1);
    });
    container.querySelector("[data-page-next]")?.addEventListener("click", () => {
      const current = Number(container.querySelector(".document-page.is-active")?.dataset.pageNumber || 1);
      setActivePage(current + 1);
    });
    container.querySelectorAll("[data-page-target]").forEach((item) => {
      item.addEventListener("click", () => {
        setActivePage(Number(item.dataset.pageTarget || 1), item.dataset.anchorTarget || null);
      });
    });
    setActivePage(1);
  });
}

function buildColumnsContent(count) {
  return {
    type: "columnsBlock",
    attrs: { count },
    content: Array.from({ length: count }, (_value, index) => ({
      type: "columnBlock",
      content: [
        {
          type: "heading",
          attrs: { level: 3 },
          content: [{ type: "text", text: `Columna ${index + 1}` }],
        },
        {
          type: "paragraph",
          content: [{ type: "text", text: `Escribe aquí el contenido de la columna ${index + 1}.` }],
        },
      ],
    })),
  };
}

function createObjectUrl(file, state) {
  const key = `${file.name}:${file.size}:${file.lastModified}`;
  if (!state.objectUrls.has(key)) {
    state.objectUrls.set(key, URL.createObjectURL(file));
  }
  return state.objectUrls.get(key);
}

function syncTransferToInput(form) {
  const input = form.querySelector("[data-asset-input]");
  if (input) input.files = form._richState.transfer.files;
}

function renderPendingAssets(form) {
  const state = form._richState;
  const container = form.querySelector("[data-inline-assets]");
  const list = form.querySelector("[data-inline-assets-list]");
  const files = [...state.transfer.files];
  if (!container || !list) return;

  container.hidden = files.length === 0;
  list.innerHTML = "";

  files.forEach((file, index) => {
    const card = document.createElement("article");
    card.className = "editor-inline-asset";

    if (file.type.startsWith("image/")) {
      const image = document.createElement("img");
      image.className = "editor-inline-asset-thumb";
      image.src = createObjectUrl(file, state);
      image.alt = file.name;
      card.append(image);
    }

    const meta = document.createElement("div");
    meta.className = "editor-inline-asset-meta";
    meta.innerHTML = `<strong>${sanitizeAssetFilename(file.name)}</strong><div class="chip-group"><span class="chip">${file.type || "archivo"}</span></div>`;
    card.append(meta);

    const actions = document.createElement("div");
    actions.className = "editor-inline-asset-actions";

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "button button-tonal";
    removeButton.textContent = "Quitar";
    removeButton.addEventListener("click", () => {
      const nextTransfer = new DataTransfer();
      [...state.transfer.files].forEach((queued, queuedIndex) => {
        if (queuedIndex !== index) nextTransfer.items.add(queued);
      });
      state.transfer = nextTransfer;
      syncTransferToInput(form);
      renderPendingAssets(form);
      updateSaveSummary(form);
    });

    actions.append(removeButton);
    card.append(actions);
    list.append(card);
  });
}

function updateSaveSummary(form) {
  const textarea = form.querySelector("[data-editor-input]");
  const branchSelect = form.querySelector('select[name="branch_name"]');
  const files = [...form._richState.transfer.files];
  const markdown = textarea?.value || "";
  const columnsCount = (markdown.match(/\[\[columns:[23]\]\]/gi) || []).length;
  const worksheetsCount = (markdown.match(/\[\[worksheet:[^\]]+\]\]/gi) || []).length;
  const branchName = branchSelect?.value || "";
  const branchLabel = formatBranchLabel(branchName);

  form.querySelector("[data-active-branch-label]")?.replaceChildren(document.createTextNode(`Espacio activo: ${branchLabel}`));
  const saveBranch = form.querySelector("[data-save-branch]");
  if (saveBranch) saveBranch.textContent = branchLabel;
  form.querySelectorAll("[data-save-columns]").forEach((node) => {
    node.textContent = pluralize(columnsCount, "bloque en columnas", "bloques en columnas");
  });
  form.querySelectorAll("[data-save-worksheets]").forEach((node) => {
    node.textContent = pluralize(worksheetsCount, "ficha enlazada", "fichas enlazadas");
  });
  form.querySelectorAll("[data-save-assets]").forEach((node) => {
    node.textContent = pluralize(files.length, "recurso pendiente", "recursos pendientes");
  });
  const assetDetail = form.querySelector("[data-save-assets-detail]");
  if (assetDetail) assetDetail.textContent = buildPendingAssetSummary(files);
  const checklist = form.querySelector("[data-save-checklist]");
  if (checklist) {
    const items = [
      "Documento actualizado.",
      `${pluralize(columnsCount, "bloque en columnas", "bloques en columnas")} detectados.`,
      `${pluralize(worksheetsCount, "ficha enlazada", "fichas enlazadas")} detectadas.`,
    ];
    if (files.length) items.push(`Se añadirán ${pluralize(files.length, "recurso nuevo", "recursos nuevos")}.`);
    checklist.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
  }
}

function setMode(form, mode) {
  form._richState.mode = mode;
  form.querySelectorAll("[data-rich-mode-button]").forEach((button) => {
    const active = button.dataset.richModeButton === mode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  form.querySelectorAll("[data-rich-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.richPanel !== mode;
    panel.classList.toggle("is-active", panel.dataset.richPanel === mode);
  });
  if (mode === "preview") {
    refreshPreview(form);
  }
}

async function refreshPreview(form) {
  const preview = form.querySelector("[data-rich-preview]");
  const textarea = form.querySelector("[data-editor-input]");
  if (!preview || !textarea) return;
  const body = new FormData();
  body.append("content", textarea.value);
  const bookId = form.querySelector("[data-editor-book-id]")?.value;
  const branchName = form.querySelector("[data-editor-branch]")?.value;
  if (bookId) body.append("book_id", bookId);
  if (branchName) body.append("branch_name", branchName);
  const response = await fetch("/books/preview", { method: "POST", body });
  preview.innerHTML = await response.text();
  initializeBookDocuments(preview);
  hydrateDraftAssetsInPreview(form);
}

function syncMarkdownFromEditor(form, editor) {
  const textarea = form.querySelector("[data-editor-input]");
  if (!textarea) return;
  textarea.value = serializeEditorDocument(editor);
  updateSaveSummary(form);
  if (form._richState.mode === "preview") {
    window.clearTimeout(form._richState.previewTimer);
    form._richState.previewTimer = window.setTimeout(() => refreshPreview(form), 180);
  }
}

function insertWorksheet(editor, slug, title) {
  editor
    .chain()
    .focus()
    .insertContent({
      type: "text",
      text: title,
      marks: [
        {
          type: "link",
          attrs: {
            href: `#worksheet-${slug}`,
            class: "worksheet-link",
            dataWorksheetSlug: slug,
          },
        },
      ],
    })
    .run();
}

function insertPendingFiles(form, editor, files, mediaTypeOverride = null) {
  const state = form._richState;
  const existing = new Set([...state.transfer.files].map((file) => `${file.name}:${file.size}:${file.lastModified}`));

  [...files].forEach((file) => {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (existing.has(key)) return;
    state.transfer.items.add(file);
    existing.add(key);
    const filename = sanitizeAssetFilename(file.name);
    const assetPath = `assets/${filename}`;

    if ((mediaTypeOverride || file.type).startsWith("image/")) {
      editor
        .chain()
        .focus()
        .setImage({
          src: createObjectUrl(file, state),
          alt: humanizeAssetName(filename),
          class: buildMediaClass(),
          dataAssetPath: assetPath,
        })
        .run();
    } else {
      editor
        .chain()
        .focus()
        .insertContent({
          type: "audioBlock",
          attrs: {
            src: createObjectUrl(file, state),
            dataAssetPath: assetPath,
          },
        })
        .run();
    }
  });

  syncTransferToInput(form);
  renderPendingAssets(form);
}

function getSelectedImage(editor) {
  const { selection } = editor.state;
  if (selection.node && selection.node.type.name === "image") {
    return { node: selection.node, pos: selection.from };
  }
  return null;
}

function showMediaToolbar(form, editor) {
  const toolbar = form.querySelector("[data-rich-media-toolbar]");
  if (!toolbar) return;
  const selected = getSelectedImage(editor);
  if (!selected) {
    toolbar.hidden = true;
    return;
  }

  const attrs = selected.node.attrs || {};
  const mediaClass = parseMediaClass(attrs.class || buildMediaClass());
  toolbar.hidden = false;
  const altInput = form.querySelector("[data-image-alt]");
  const alignInput = form.querySelector("[data-image-align]");
  const sizeInput = form.querySelector("[data-image-size]");
  if (altInput) altInput.value = attrs.alt || "";
  if (alignInput) alignInput.value = mediaClass.align;
  if (sizeInput) sizeInput.value = mediaClass.size;
}

function initializeSaveDialog(form) {
  const dialog = form.querySelector("[data-save-dialog]");
  const openButton = form.querySelector("[data-open-save-dialog]");
  const closeButton = form.querySelector("[data-close-save-dialog]");

  const openDialog = () => {
    updateSaveSummary(form);
    if (dialog && typeof dialog.showModal === "function") {
      dialog.showModal();
      form.querySelector("[data-save-commit-input]")?.focus();
      return;
    }
    form.requestSubmit();
  };

  openButton?.addEventListener("click", openDialog);
  closeButton?.addEventListener("click", () => dialog?.close());
  form.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      openDialog();
    }
  });
}

function initializeRichEditor(form) {
  const hiddenTextarea = form.querySelector("[data-editor-input]");
  const host = form.querySelector("[data-rich-editor]");
  if (!hiddenTextarea || !host) return;

  form._richState = {
    mode: "edit",
    transfer: new DataTransfer(),
    objectUrls: new Map(),
    previewTimer: null,
  };

  const initialHtml = markdownToEditorHtml(hiddenTextarea.value, form);

  const editor = new Editor({
    element: host,
    extensions: [
      StarterKit.configure({
        horizontalRule: false,
      }),
      Placeholder.configure({
        placeholder: "Empieza a escribir el material aquí. Usa la cinta superior para estructurarlo.",
      }),
      WorksheetLink.configure({
        openOnClick: false,
      }),
      RichImage,
      AudioBlock,
      PageBreak,
      ColumnsBlock,
      ColumnBlock,
    ],
    content: initialHtml,
    onUpdate: () => syncMarkdownFromEditor(form, editor),
    onSelectionUpdate: () => showMediaToolbar(form, editor),
  });

  form._richState.editor = editor;
  syncMarkdownFromEditor(form, editor);
  renderPendingAssets(form);
  showMediaToolbar(form, editor);

  form.querySelectorAll("[data-rich-mode-button]").forEach((button) => {
    button.addEventListener("click", () => setMode(form, button.dataset.richModeButton || "edit"));
  });

  form.querySelector('select[name="branch_name"]')?.addEventListener("change", (event) => {
    const branchName = event.target.value || "";
    const hiddenBranch = form.querySelector("[data-editor-branch]");
    if (hiddenBranch) hiddenBranch.value = branchName;
    updateSaveSummary(form);
  });

  form.querySelectorAll("[data-rich-command]").forEach((button) => {
    button.addEventListener("click", () => {
      const command = button.dataset.richCommand;
      if (command === "paragraph") editor.chain().focus().setParagraph().run();
      if (command === "heading") editor.chain().focus().toggleHeading({ level: 2 }).run();
      if (command === "bold") editor.chain().focus().toggleBold().run();
      if (command === "italic") editor.chain().focus().toggleItalic().run();
      if (command === "bulletList") editor.chain().focus().toggleBulletList().run();
      if (command === "blockquote") editor.chain().focus().toggleBlockquote().run();
      if (command === "columns-2") editor.chain().focus().insertContent(buildColumnsContent(2)).run();
      if (command === "columns-3") editor.chain().focus().insertContent(buildColumnsContent(3)).run();
      if (command === "pagebreak") editor.chain().focus().insertContent({ type: "pageBreak" }).run();
      if (command === "worksheet") setMode(form, "library");
      if (command === "image") {
        form.querySelector("[data-asset-input]")?.click();
      }
      if (command === "audio") {
        form.querySelector("[data-asset-input]")?.click();
      }
    });
  });

  form.querySelector("[data-asset-input]")?.addEventListener("change", (event) => {
    insertPendingFiles(form, editor, event.target.files || []);
  });

  form.querySelector("[data-asset-picker]")?.addEventListener("click", () => {
    form.querySelector("[data-asset-input]")?.click();
  });

  [form.querySelector("[data-asset-dropzone]"), form.querySelector("[data-editor-surface]"), host].forEach((target) => {
    target?.addEventListener("dragover", (event) => {
      event.preventDefault();
    });
    target?.addEventListener("drop", (event) => {
      event.preventDefault();
      insertPendingFiles(form, editor, event.dataTransfer?.files || []);
    });
  });

  form.querySelectorAll("[data-insert-worksheet]").forEach((button) => {
    button.addEventListener("click", () => {
      insertWorksheet(editor, button.dataset.worksheetSlug || "", button.dataset.worksheetTitle || "Ficha");
      setMode(form, "edit");
    });
  });

  form.querySelectorAll("[data-insert-asset]").forEach((button) => {
    button.addEventListener("click", () => {
      const mediaType = button.dataset.assetMediaType || "";
      const filename = sanitizeAssetFilename(button.dataset.assetFilename || "recurso");
      const assetPath = `assets/${filename}`;
      const publicUrl = button.dataset.assetPublicUrl || resolveAssetUrl(form, assetPath);
      if (mediaType.startsWith("image/")) {
        editor
          .chain()
          .focus()
          .setImage({
            src: publicUrl,
            alt: humanizeAssetName(filename),
            class: buildMediaClass(),
            dataAssetPath: assetPath,
          })
          .run();
      } else {
        editor
          .chain()
          .focus()
          .insertContent({
            type: "audioBlock",
            attrs: {
              src: publicUrl,
              dataAssetPath: assetPath,
            },
          })
          .run();
      }
      setMode(form, "edit");
    });
  });

  const updateSelectedImage = () => {
    const selected = getSelectedImage(editor);
    if (!selected) return;
    const alt = form.querySelector("[data-image-alt]")?.value || "";
    const align = form.querySelector("[data-image-align]")?.value || "center";
    const size = form.querySelector("[data-image-size]")?.value || "100";
    editor.commands.updateAttributes("image", {
      alt,
      class: buildMediaClass(align, size),
    });
  };

  form.querySelector("[data-image-alt]")?.addEventListener("input", updateSelectedImage);
  form.querySelector("[data-image-align]")?.addEventListener("change", updateSelectedImage);
  form.querySelector("[data-image-size]")?.addEventListener("change", updateSelectedImage);
  form.querySelector("[data-rich-remove-selected-media]")?.addEventListener("click", () => {
    editor.commands.deleteSelection();
  });

  initializeSaveDialog(form);
}

document.addEventListener("DOMContentLoaded", () => {
  initializeBookDocuments(document);
  document.querySelectorAll("[data-rich-markdown-editor]").forEach((form) => initializeRichEditor(form));
});
