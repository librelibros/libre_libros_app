import { Editor } from "@tiptap/core";
import { editorExtensions } from "./extensions.mjs";
import { prepareDocument, importText } from "./contract.mjs";
import { loadDocument, checkedSerialization } from "./document.mjs";
import { initializeIntegrityControls, setStatus } from "./controls.mjs";

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
  return `/books/${bookId}/${path.split('/').map(encodeURIComponent).join('/')}?${new URLSearchParams({branch: branchName})}`;
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
      const positions = [];
      state.editor.state.doc.descendants((node, pos) => { if (node.attrs.dataAssetPath === `assets/${file.name}`) positions.push({pos, size:node.nodeSize}); });
      let transaction = state.editor.state.tr;
      positions.reverse().forEach(({pos,size}) => { transaction = transaction.delete(pos,pos+size); });
      if (positions.length) state.editor.view.dispatch(transaction);
      syncTransferToInput(form);
      renderPendingAssets(form);
      syncMarkdownFromEditor(form, state.editor);
    });

    actions.append(removeButton);
    card.append(actions);
    list.append(card);
  });
}

function updateSaveSummary(form) {
  const textarea = form.querySelector("[data-editor-input]");
  const branchSelect = form.querySelector('[name="branch_name"]');
  const files = [...form._richState.transfer.files];
  const markdown = textarea?.value || "";
  const columnsCount = (markdown.match(/\[\[columns:[23]\]\]/gi) || []).length;
  const worksheetsCount = (markdown.match(/\[\[worksheet:[^\]]+\]\]/gi) || []).length;
  const branchName = branchSelect?.value || "";
  const branchLabel = branchSelect?.dataset.branchLabel || formatBranchLabel(branchName);

  form.querySelector("[data-active-branch-label]")?.replaceChildren(document.createTextNode(branchLabel));
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
  const state = form._richState;
  state.previewAbort?.abort();
  const controller = new AbortController();
  state.previewAbort = controller;
  setStatus(form, "Preparando lectura…");
  try {
    const response = await fetch("/books/preview", window.LibreLibrosCSRF.options("/books/preview", { method: "POST", body, signal: controller.signal }));
    if (!response.ok || response.redirected) throw new Error('preview');
    const html = await response.text();
    if (controller.signal.aborted) return;
    preview.innerHTML = html;
    initializeBookDocuments(preview);
    hydrateDraftAssetsInPreview(form);
    setStatus(form, "Lectura actualizada. No es una previsualización exacta del PDF.");
  } catch (error) {
    if (error.name !== 'AbortError') setStatus(form, "No se pudo actualizar la lectura. Tu borrador sigue aquí; vuelve a pulsar Lectura para reintentar.");
  }
}

function syncMarkdownFromEditor(form, editor) {
  const textarea = form.querySelector("[data-editor-input]");
  if (!textarea) return;
  const state = form._richState;
  if (state.blocked) return;
  try {
    const unchanged = JSON.stringify(editor.getJSON()) === state.initialJSON;
    textarea.value = unchanged ? state.original : checkedSerialization(editor.getJSON());
    state.invalid = false;
    state.dirty = textarea.value !== state.original || state.transfer.files.length > 0;
    setStatus(form, state.dirty ? 'Cambios sin guardar.' : 'Sin cambios. Se conserva el archivo original.');
  } catch (error) {
    state.invalid = true;
    state.dirty = true;
    setStatus(form, error.message + ' El último borrador válido se conserva; Guardar está bloqueado hasta corregirlo.');
  }
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
  if (state.blocked || state.saving) return;
  const used = new Set([...state.transfer.files].map(file => file.name));
  form.querySelectorAll('[data-asset-filename]').forEach(button => used.add(button.dataset.assetFilename));
  editor.state.doc.descendants(node => { if (node.attrs.dataAssetPath) used.add(node.attrs.dataAssetPath.split('/').pop()); });
  [...files].forEach((originalFile) => {
    if (!/^(image\/(png|jpeg|webp|gif)|audio\/mpeg)$/.test(originalFile.type) || originalFile.size > 10 * 1024 * 1024) {
      setStatus(form, 'Recurso no añadido: usa PNG, JPEG, WebP, GIF o MP3 hasta 10 MB. SVG y documentos no se importan como recursos.'); return;
    }
    const extension = {'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp','image/gif':'.gif','audio/mpeg':'.mp3'}[originalFile.type];
    const stem = slugifyName(originalFile.name.replace(/\.[^.]*$/, '')) || 'recurso';
    let filename = stem + extension, suffix = 2;
    while (used.has(filename)) filename = `${stem}-${suffix++}${extension}`;
    used.add(filename);
    const file = new File([originalFile], filename, {type:originalFile.type, lastModified:originalFile.lastModified});
    state.transfer.items.add(file);
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
    if (form._richState.invalid || form._richState.saving) { setStatus(form, 'Revisa el formato antes de guardar o espera al guardado actual.'); return; }
    if (dialog && typeof dialog.showModal === "function") {
      if (!dialog.open) dialog.showModal();
      form.querySelector("[data-save-commit-input]")?.focus();
      return;
    }
    form.requestSubmit();
  };

  openButton?.addEventListener("click", openDialog);
  closeButton?.addEventListener("click", () => dialog?.close());
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      openDialog();
    }
  });
}

function initializeRichEditor(form) {
  if (form._richState) return;
  const hiddenTextarea = form.querySelector("[data-editor-input]");
  const host = form.querySelector("[data-rich-editor]");
  if (!hiddenTextarea || !host) return;

  form._richState = {
    mode: "edit",
    transfer: new DataTransfer(),
    objectUrls: new Map(),
    previewTimer: null,
    original: hiddenTextarea.value,
    dirty: false,
    invalid: false,
    blocked: false,
  };
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  form.prepend(status);
  form._richState.status = status;
  const prepared = loadDocument(hiddenTextarea.value, path => resolveAssetUrl(form, path));
  const initialHtml = prepared.ok ? prepared.html : '<p></p>';
  form._richState.blocked = !prepared.ok;

  const editor = new Editor({
    element: host,
    extensions: editorExtensions(),
    content: initialHtml,
    editable: prepared.ok,
    editorProps: {
      handlePaste(_view, event) {
        // Office HTML can lose nodes before a transaction reaches onUpdate.
        if (event.clipboardData?.types.includes('text/html') || event.clipboardData?.files.length) {
          event.preventDefault();
          setStatus(form, 'Pegado con formato bloqueado para evitar pérdidas. Usa pegar como texto (Ctrl/Cmd+Shift+V) o Importar .md/.txt.');
          return true;
        }
        return false;
      },
      handleDrop(_view, event) { if (!event.dataTransfer?.files.length) { event.preventDefault(); setStatus(form, 'Para mover contenido usa cortar y pegar como texto.'); return true; } return false; },
    },
    onUpdate: () => syncMarkdownFromEditor(form, editor),
    onSelectionUpdate: () => showMediaToolbar(form, editor),
  });

  form._richState.editor = editor;
  form._richState.initialJSON = JSON.stringify(editor.getJSON());
  if (!prepared.ok) {
    host.hidden = true;
    const originalView = document.createElement('textarea');
    originalView.readOnly = true;
    originalView.value = hiddenTextarea.value;
    originalView.rows = 16;
    originalView.setAttribute('aria-label', 'Original conservado (solo lectura)');
    host.after(originalView);
    form.querySelectorAll('[data-rich-command], [data-insert-asset], [data-insert-worksheet], [data-asset-picker]').forEach(button => { button.disabled = true; });
    setStatus(form, 'Edición visual bloqueada para no perder contenido. ' + prepared.warnings.join(' ') + ' Puedes descargar el original.');
  } else setStatus(form, 'Sin cambios. El original se conservará al guardar. ' + prepared.warnings.join(' '));
  initializeIntegrityControls(form, editor);
  updateSaveSummary(form);
  renderPendingAssets(form);
  showMediaToolbar(form, editor);

  form.querySelectorAll("[data-rich-mode-button]").forEach((button) => {
    button.addEventListener("click", () => setMode(form, button.dataset.richModeButton || "edit"));
  });

  form.querySelector('[name="branch_name"]')?.addEventListener("change", (event) => {
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
      event.stopPropagation();
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
