const actions = {
  heading: "## ",
  bold: "**texto**",
  italic: "_texto_",
  list: "- elemento",
  quote: "> cita",
  pagebreak: "\n\n<!-- pagebreak -->\n\n",
  audio: '<audio controls src="assets/audio.mp3"></audio>',
  worksheet: "[[worksheet:slug-de-la-ficha|Ir a la ficha]]",
};

function insertSnippet(textarea, snippet) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const before = textarea.value.slice(0, start);
  const after = textarea.value.slice(end);
  textarea.value = `${before}${snippet}${after}`;
  textarea.selectionStart = textarea.selectionEnd = start + snippet.length;
  textarea.dispatchEvent(new Event("input"));
}

async function copyText(snippet) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(snippet);
    return;
  }
  throw new Error("Clipboard API not available");
}

async function refreshPreview(form) {
  const textarea = form.querySelector("[data-editor-input]");
  const preview = form.querySelector("[data-editor-preview]");
  if (!textarea || !preview) return;
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

function sanitizeAssetFilename(filename) {
  const lastDot = filename.lastIndexOf(".");
  const stem = lastDot === -1 ? filename : filename.slice(0, lastDot);
  const extension = lastDot === -1 ? "" : filename.slice(lastDot).toLowerCase();
  return `${slugifyName(stem) || "asset"}${extension}`;
}

function buildImageSnippet(filename, options = {}) {
  const safeName = sanitizeAssetFilename(filename);
  const altText = (options.altText || humanizeAssetName(safeName) || safeName).trim();
  const align = options.align || "center";
  const size = options.size || "100";
  const classes = ["doc-image", `doc-align-${align}`, `doc-w-${size}`];
  return `![${altText}](assets/${safeName}){: .${classes.join(" .")}}`;
}

function buildAudioSnippet(filename) {
  const safeName = sanitizeAssetFilename(filename);
  return `<audio controls src="assets/${safeName}"></audio>`;
}

function buildAssetSnippet(asset, options = {}) {
  if (!asset) return "";
  if ((asset.mediaType || "").startsWith("image/")) {
    return buildImageSnippet(asset.filename, options);
  }
  if (asset.mediaType === "audio/mpeg") {
    return buildAudioSnippet(asset.filename);
  }
  return asset.rawSnippet || `[${asset.filename}](assets/${sanitizeAssetFilename(asset.filename)})`;
}

function buildColumnsSnippet(columnCount) {
  const totalColumns = columnCount === 3 ? 3 : 2;
  const blocks = Array.from({ length: totalColumns }, (_value, index) => {
    const currentColumn = index + 1;
    return `### Columna ${currentColumn}\n\nEscribe aqui el contenido de la columna ${currentColumn}.`;
  });
  return `[[columns:${totalColumns}]]\n${blocks.join("\n[[col]]\n")}\n[[/columns]]`;
}

function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function setActivePage(container, nextPageNumber, anchorId = null) {
  const pages = [...container.querySelectorAll("[data-book-page]")];
  if (!pages.length) return;
  const boundedPageNumber = Math.min(Math.max(nextPageNumber, 1), pages.length);

  pages.forEach((page) => {
    const isActive = Number(page.dataset.pageNumber) === boundedPageNumber;
    page.classList.toggle("is-active", isActive);
  });

  const indicator = container.querySelector("[data-page-indicator]");
  if (indicator) {
    indicator.textContent = `Pagina ${boundedPageNumber} de ${pages.length}`;
  }

  const previous = container.querySelector("[data-page-prev]");
  const next = container.querySelector("[data-page-next]");
  if (previous) previous.disabled = boundedPageNumber === 1;
  if (next) next.disabled = boundedPageNumber === pages.length;

  container.querySelectorAll("[data-page-target]").forEach((item) => {
    const matches = Number(item.dataset.pageTarget) === boundedPageNumber;
    item.classList.toggle("is-active", matches);
  });

  if (anchorId) {
    const anchor = container.querySelector(`#${anchorId}`);
    anchor?.scrollIntoView({ block: "start", behavior: "smooth" });
  }
}

function initializeBookDocuments(root = document) {
  root.querySelectorAll("[data-book-document]").forEach((container) => {
    if (container.dataset.documentReady === "true") return;
    container.dataset.documentReady = "true";

    const pages = [...container.querySelectorAll("[data-book-page]")];
    if (!pages.length) return;

    const previous = container.querySelector("[data-page-prev]");
    const next = container.querySelector("[data-page-next]");
    previous?.addEventListener("click", () => {
      const activePage = container.querySelector(".document-page.is-active");
      const pageNumber = Number(activePage?.dataset.pageNumber || 1);
      setActivePage(container, pageNumber - 1);
    });
    next?.addEventListener("click", () => {
      const activePage = container.querySelector(".document-page.is-active");
      const pageNumber = Number(activePage?.dataset.pageNumber || 1);
      setActivePage(container, pageNumber + 1);
    });

    container.querySelectorAll("[data-page-target]").forEach((item) => {
      item.addEventListener("click", () => {
        setActivePage(container, Number(item.dataset.pageTarget || 1), item.dataset.anchorTarget || null);
      });
    });

    setActivePage(container, 1);
  });
}

function createAssetKey(asset) {
  return `${asset.filename}:${asset.mediaType || ""}:${asset.source || ""}`;
}

function assetFromButton(button) {
  return {
    filename: button.dataset.assetFilename || "",
    mediaType: button.dataset.assetMediaType || "",
    rawSnippet: button.dataset.assetSnippet || "",
    source: "library",
  };
}

function getMediaOptions(form) {
  return {
    altText: form.querySelector("[data-image-alt]")?.value || "",
    align: form.querySelector("[data-image-align]")?.value || "center",
    size: form.querySelector("[data-image-size]")?.value || "100",
  };
}

function assetIdentity(asset) {
  return `${sanitizeAssetFilename(asset?.filename || "")}:${asset?.mediaType || ""}:${asset?.source || ""}`;
}

function extractAssetFilenameFromUrl(url) {
  try {
    const normalized = new URL(url, window.location.origin);
    return sanitizeAssetFilename(normalized.pathname.split("/").pop() || "");
  } catch (_error) {
    return sanitizeAssetFilename((url || "").split("?")[0].split("/").pop() || "");
  }
}

function createObjectUrlForFile(form, file) {
  const key = `${file.name}:${file.size}:${file.lastModified}`;
  const state = form._editorState;
  if (!state.objectUrls.has(key)) {
    state.objectUrls.set(key, URL.createObjectURL(file));
  }
  return state.objectUrls.get(key);
}

function syncObjectUrls(form) {
  const state = form._editorState;
  const activeKeys = new Set([...state.transfer.files].map((file) => `${file.name}:${file.size}:${file.lastModified}`));
  [...state.objectUrls.keys()].forEach((key) => {
    if (!activeKeys.has(key)) {
      URL.revokeObjectURL(state.objectUrls.get(key));
      state.objectUrls.delete(key);
    }
  });
}

function buildPendingAssetUrlMap(form) {
  const urlMap = new Map();
  [...form._editorState.transfer.files].forEach((file) => {
    urlMap.set(sanitizeAssetFilename(file.name), createObjectUrlForFile(form, file));
  });
  return urlMap;
}

function hydrateDraftAssetsInPreview(form) {
  const preview = form.querySelector("[data-editor-preview]");
  if (!preview) return;

  const assetUrls = buildPendingAssetUrlMap(form);
  if (!assetUrls.size) return;

  preview.querySelectorAll("img[src]").forEach((image) => {
    const filename = extractAssetFilenameFromUrl(image.getAttribute("src") || "");
    const objectUrl = assetUrls.get(filename);
    if (objectUrl) image.src = objectUrl;
  });

  preview.querySelectorAll("audio[src]").forEach((audio) => {
    const filename = extractAssetFilenameFromUrl(audio.getAttribute("src") || "");
    const objectUrl = assetUrls.get(filename);
    if (objectUrl) audio.src = objectUrl;
  });
}

function setEditorTab(form, tabName) {
  form._editorState.activeTab = tabName;
  form.querySelectorAll("[data-editor-tab-button]").forEach((button) => {
    const isActive = button.dataset.editorTabButton === tabName;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  form.querySelectorAll("[data-editor-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.editorPanel !== tabName;
  });
}

function syncBranchPreviewState(form) {
  const branchSelect = form.querySelector('select[name="branch_name"]');
  const branchName = branchSelect?.value || "";
  const hiddenBranch = form.querySelector("[data-editor-branch]");
  const branchLabel = form.querySelector("[data-active-branch-label]");
  if (hiddenBranch) hiddenBranch.value = branchName;
  if (branchLabel) branchLabel.textContent = `Rama activa: ${branchName}`;
}

function updateSaveDialogSummary(form) {
  const textarea = form.querySelector("[data-editor-input]");
  const branchSelect = form.querySelector('select[name="branch_name"]');
  const branchName = branchSelect?.value || form.querySelector("[data-editor-branch]")?.value || "";
  const files = [...(form._editorState?.transfer?.files || [])];
  const columnsCount = (textarea?.value.match(/\[\[columns:[23]\]\]/gi) || []).length;
  const worksheetsCount = (textarea?.value.match(/\[\[worksheet:[^\]]+\]\]/gi) || []).length;

  const branchTarget = form.querySelector("[data-save-branch]");
  const columnsTarget = form.querySelector("[data-save-columns]");
  const worksheetsTarget = form.querySelector("[data-save-worksheets]");
  const assetsTarget = form.querySelector("[data-save-assets]");
  const assetsDetailTarget = form.querySelector("[data-save-assets-detail]");
  const checklist = form.querySelector("[data-save-checklist]");

  if (branchTarget) branchTarget.textContent = branchName;
  if (columnsTarget) columnsTarget.textContent = `${pluralize(columnsCount, "bloque en columnas", "bloques en columnas")}`;
  if (worksheetsTarget) worksheetsTarget.textContent = `${pluralize(worksheetsCount, "enlace a ficha", "enlaces a fichas")}`;
  if (assetsTarget) assetsTarget.textContent = `${pluralize(files.length, "asset pendiente", "assets pendientes")}`;

  if (assetsDetailTarget) {
    assetsDetailTarget.textContent = files.length
      ? `Archivos nuevos: ${files.map((file) => sanitizeAssetFilename(file.name)).join(", ")}.`
      : "Sin archivos nuevos en esta edición.";
  }

  if (checklist) {
    const items = [
      "Documento Markdown actualizado.",
      `${pluralize(columnsCount, "bloque en columnas", "bloques en columnas")} detectados.`,
      `${pluralize(worksheetsCount, "enlace a ficha", "enlaces a fichas")} detectados.`,
    ];
    if (files.length) {
      items.push(`Se versionarán ${pluralize(files.length, "archivo nuevo", "archivos nuevos")}.`);
    }
    checklist.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
  }
}

function initializeSaveDialog(form, textarea) {
  const dialog = form.querySelector("[data-save-dialog]");
  const openButton = form.querySelector("[data-open-save-dialog]");
  const closeButton = form.querySelector("[data-close-save-dialog]");
  const commitInput = form.querySelector("[data-save-commit-input]");

  const openDialog = () => {
    updateSaveDialogSummary(form);
    if (!dialog || typeof dialog.showModal !== "function") {
      form.requestSubmit();
      return;
    }
    dialog.showModal();
    commitInput?.focus();
  };

  openButton?.addEventListener("click", openDialog);
  closeButton?.addEventListener("click", () => dialog?.close());
  form.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      openDialog();
    }
  });

  form.querySelector('select[name="branch_name"]')?.addEventListener("change", () => {
    syncBranchPreviewState(form);
    updateSaveDialogSummary(form);
    refreshPreview(form);
  });

  textarea.addEventListener("input", () => updateSaveDialogSummary(form));
  syncBranchPreviewState(form);
  updateSaveDialogSummary(form);
}

function renderSelectedAsset(form) {
  const state = form._editorState;
  const nameInput = form.querySelector("[data-selected-asset-name]");
  const altInput = form.querySelector("[data-image-alt]");
  const alignInput = form.querySelector("[data-image-align]");
  const sizeInput = form.querySelector("[data-image-size]");
  const hint = form.querySelector("[data-selected-asset-hint]");
  const selected = state.selectedAsset;

  if (!nameInput || !altInput || !alignInput || !sizeInput || !hint) return;

  if (!selected) {
    nameInput.value = "";
    altInput.value = "";
    altInput.disabled = false;
    alignInput.disabled = false;
    sizeInput.disabled = false;
    hint.textContent = "Selecciona una imagen de la biblioteca o arrastra un archivo para preparar el bloque.";
    return;
  }

  nameInput.value = sanitizeAssetFilename(selected.filename);
  if ((selected.mediaType || "").startsWith("image/")) {
    if (!altInput.value || altInput.dataset.assetKey !== createAssetKey(selected)) {
      altInput.value = humanizeAssetName(sanitizeAssetFilename(selected.filename));
    }
    altInput.dataset.assetKey = createAssetKey(selected);
    altInput.disabled = false;
    alignInput.disabled = false;
    sizeInput.disabled = false;
    hint.textContent = "La imagen se insertará con clases de maquetación para moverla a izquierda, derecha o centrarla y ajustar su ancho.";
  } else {
    altInput.value = "";
    altInput.disabled = true;
    alignInput.disabled = true;
    sizeInput.disabled = true;
    hint.textContent = "Los audios se insertan como bloque de reproducción. Las opciones de posición y tamaño no se aplican.";
  }
}

function setSelectedAsset(form, asset) {
  form._editorState.selectedAsset = asset;
  renderSelectedAsset(form);
  renderInlineAssets(form);
}

function insertSelectedAsset(form, textarea, assetOverride = null) {
  const asset = assetOverride || form._editorState.selectedAsset;
  if (!asset) return false;
  const snippet = buildAssetSnippet(asset, getMediaOptions(form));
  insertSnippet(textarea, `\n\n${snippet}\n\n`);
  return true;
}

function syncTransferToInput(form) {
  const input = form.querySelector("[data-asset-input]");
  if (!input) return;
  input.files = form._editorState.transfer.files;
}

function renderInlineAssets(form) {
  const state = form._editorState;
  const container = form.querySelector("[data-inline-assets]");
  const list = form.querySelector("[data-inline-assets-list]");
  const textarea = form.querySelector("[data-editor-input]");
  if (!container || !list || !textarea) return;

  const files = [...state.transfer.files];
  container.hidden = files.length === 0;
  list.innerHTML = "";

  const mediaOptions = getMediaOptions(form);

  files.forEach((file) => {
    const asset = {
      filename: file.name,
      mediaType: file.type || "",
      source: "pending",
    };

    const card = document.createElement("article");
    card.className = "editor-inline-asset";
    if (state.selectedAsset && assetIdentity(state.selectedAsset) === assetIdentity(asset)) {
      card.classList.add("is-selected");
    }

    if (file.type.startsWith("image/")) {
      const image = document.createElement("img");
      image.className = "editor-inline-asset-thumb";
      image.alt = file.name;
      image.src = createObjectUrlForFile(form, file);
      card.append(image);
    }

    const meta = document.createElement("div");
    meta.className = "editor-inline-asset-meta";
    const title = document.createElement("strong");
    title.textContent = sanitizeAssetFilename(file.name);
    meta.append(title);

    const chips = document.createElement("div");
    chips.className = "chip-group";
    const mediaChip = document.createElement("span");
    mediaChip.className = "chip";
    mediaChip.textContent = file.type || "archivo";
    chips.append(mediaChip);

    if (file.type.startsWith("image/")) {
      const alignChip = document.createElement("span");
      alignChip.className = "chip";
      alignChip.textContent = `Alineación ${mediaOptions.align}`;
      const sizeChip = document.createElement("span");
      sizeChip.className = "chip";
      sizeChip.textContent = `${mediaOptions.size}%`;
      chips.append(alignChip, sizeChip);
    }

    meta.append(chips);
    card.append(meta);

    const actionsRow = document.createElement("div");
    actionsRow.className = "editor-inline-asset-actions";

    const prepareButton = document.createElement("button");
    prepareButton.type = "button";
    prepareButton.className = "button button-tonal";
    prepareButton.textContent = "Preparar";
    prepareButton.addEventListener("click", () => {
      setSelectedAsset(form, asset);
      setEditorTab(form, "media");
    });

    const insertButton = document.createElement("button");
    insertButton.type = "button";
    insertButton.className = "button button-tonal";
    insertButton.textContent = "Insertar";
    insertButton.addEventListener("click", () => {
      setSelectedAsset(form, asset);
      insertSelectedAsset(form, textarea, asset);
    });

    actionsRow.append(prepareButton, insertButton);
    card.append(actionsRow);
    list.append(card);
  });
}

function renderPendingAssets(form, textarea) {
  const state = form._editorState;
  const pending = form.querySelector("[data-pending-assets]");
  const list = form.querySelector("[data-pending-assets-list]");
  if (!pending || !list) return;

  const files = [...state.transfer.files];
  syncObjectUrls(form);
  pending.hidden = files.length === 0;
  list.innerHTML = "";

  files.forEach((file, index) => {
    const asset = {
      filename: file.name,
      mediaType: file.type || "",
      source: "pending",
      rawSnippet: buildAssetSnippet({ filename: file.name, mediaType: file.type || "" }),
    };

    const card = document.createElement("article");
    card.className = "comment stack compact pending-asset-card";

    const head = document.createElement("div");
    head.className = "comment-head";
    const title = document.createElement("strong");
    title.textContent = sanitizeAssetFilename(file.name);
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = file.type || "archivo";
    head.append(title, chip);
    card.append(head);

    if (file.type.startsWith("image/")) {
      const image = document.createElement("img");
      image.className = "asset-preview";
      image.alt = file.name;
      image.src = createObjectUrlForFile(form, file);
      card.append(image);
    }

    const snippetCode = document.createElement("code");
    snippetCode.textContent = buildAssetSnippet(asset, getMediaOptions(form));
    card.append(snippetCode);

    const actionsRow = document.createElement("div");
    actionsRow.className = "actions";

    const prepareButton = document.createElement("button");
    prepareButton.type = "button";
    prepareButton.className = "button button-tonal";
    prepareButton.textContent = "Preparar bloque";
    prepareButton.addEventListener("click", () => setSelectedAsset(form, asset));

    const insertButton = document.createElement("button");
    insertButton.type = "button";
    insertButton.className = "button button-tonal";
    insertButton.textContent = "Insertar";
    insertButton.addEventListener("click", () => {
      setSelectedAsset(form, asset);
      insertSelectedAsset(form, textarea, asset);
    });

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "button button-tonal";
    removeButton.textContent = "Quitar";
    removeButton.addEventListener("click", () => {
      const nextTransfer = new DataTransfer();
      [...state.transfer.files].forEach((queuedFile, queuedIndex) => {
        if (queuedIndex !== index) nextTransfer.items.add(queuedFile);
      });
      state.transfer = nextTransfer;
      if (state.selectedAsset && state.selectedAsset.source === "pending" && sanitizeAssetFilename(state.selectedAsset.filename) === sanitizeAssetFilename(file.name)) {
        state.selectedAsset = null;
        renderSelectedAsset(form);
      }
      syncTransferToInput(form);
      renderPendingAssets(form, textarea);
    });

    actionsRow.append(prepareButton, insertButton, removeButton);
    card.append(actionsRow);
    list.append(card);
  });

  renderInlineAssets(form);
  hydrateDraftAssetsInPreview(form);
  updateSaveDialogSummary(form);
}

function appendFilesToEditor(form, textarea, files, options = {}) {
  const state = form._editorState;
  const insertSnippets = options.insertSnippets !== false;
  const newAssets = [];
  const existingKeys = new Set([...state.transfer.files].map((file) => `${file.name}:${file.size}:${file.lastModified}`));

  [...files].forEach((file) => {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (!existingKeys.has(key)) {
      state.transfer.items.add(file);
      existingKeys.add(key);
      newAssets.push({
        filename: file.name,
        mediaType: file.type || "",
        source: "pending",
      });
    }
  });

  if (!newAssets.length) return;

  syncTransferToInput(form);
  renderPendingAssets(form, textarea);
  setSelectedAsset(form, newAssets[newAssets.length - 1]);

  if (insertSnippets) {
    const snippets = newAssets
      .map((asset) => buildAssetSnippet(asset))
      .map((snippet) => `\n\n${snippet}\n\n`)
      .join("");
    insertSnippet(textarea, snippets);
  }
}

function initializeMediaStudio(form, textarea) {
  const input = form.querySelector("[data-asset-input]");
  const dropzone = form.querySelector("[data-asset-dropzone]");
  const picker = form.querySelector("[data-asset-picker]");
  const surface = form.querySelector("[data-editor-surface]");

  form._editorState = {
    transfer: new DataTransfer(),
    objectUrls: new Map(),
    selectedAsset: null,
    activeTab: "preview",
  };

  function handleFileDrop(files) {
    appendFilesToEditor(form, textarea, files);
    setEditorTab(form, "media");
  }

  picker?.addEventListener("click", () => input?.click());
  input?.addEventListener("change", () => {
    appendFilesToEditor(form, textarea, input.files);
    setEditorTab(form, "media");
  });

  [dropzone, surface, textarea].forEach((target) => {
    target?.addEventListener("dragover", (event) => {
      event.preventDefault();
      event.stopPropagation();
      surface?.classList.add("is-dragover");
      dropzone?.classList.add("is-dragover");
    });
    target?.addEventListener("dragleave", () => {
      surface?.classList.remove("is-dragover");
      dropzone?.classList.remove("is-dragover");
    });
    target?.addEventListener("drop", (event) => {
      event.preventDefault();
      event.stopPropagation();
      surface?.classList.remove("is-dragover");
      dropzone?.classList.remove("is-dragover");
      handleFileDrop(event.dataTransfer?.files || []);
    });
  });

  dropzone?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input?.click();
    }
  });

  form.querySelector("[data-insert-selected-asset]")?.addEventListener("click", () => {
    insertSelectedAsset(form, textarea);
  });

  form.querySelector("[data-copy-selected-asset]")?.addEventListener("click", async () => {
    const asset = form._editorState.selectedAsset;
    if (!asset) return;
    await copyText(buildAssetSnippet(asset, getMediaOptions(form)));
  });

  form.querySelectorAll("[data-editor-tab-button]").forEach((button) => {
    button.addEventListener("click", () => {
      setEditorTab(form, button.dataset.editorTabButton || "preview");
    });
  });

  form.querySelectorAll("[data-select-asset]").forEach((button) => {
    button.addEventListener("click", () => {
      setSelectedAsset(form, assetFromButton(button));
      setEditorTab(form, "media");
    });
  });

  form.querySelectorAll("[data-insert-asset]").forEach((button) => {
    button.addEventListener("click", () => {
      const asset = assetFromButton(button);
      setSelectedAsset(form, asset);
      insertSelectedAsset(form, textarea, asset);
    });
  });

  form.querySelectorAll("[data-insert-worksheet]").forEach((button) => {
    button.addEventListener("click", () => {
      insertSnippet(textarea, `\n\n${button.dataset.worksheetSnippet || actions.worksheet}\n\n`);
      setEditorTab(form, "preview");
    });
  });

  [
    form.querySelector("[data-image-alt]"),
    form.querySelector("[data-image-align]"),
    form.querySelector("[data-image-size]"),
  ].forEach((control) => {
    control?.addEventListener("input", () => {
      renderPendingAssets(form, textarea);
      renderSelectedAsset(form);
    });
    control?.addEventListener("change", () => {
      renderPendingAssets(form, textarea);
      renderSelectedAsset(form);
    });
  });

  setEditorTab(form, "preview");
  renderSelectedAsset(form);
  renderPendingAssets(form, textarea);
}

document.addEventListener("DOMContentLoaded", () => {
  initializeBookDocuments(document);

  document.querySelectorAll("[data-markdown-editor]").forEach((form) => {
    const textarea = form.querySelector("[data-editor-input]");
    if (!textarea) return;

    initializeMediaStudio(form, textarea);
    initializeSaveDialog(form, textarea);

    form.querySelectorAll("[data-editor-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.dataset.editorAction;
        if (action === "columns-2") {
          insertSnippet(textarea, `\n\n${buildColumnsSnippet(2)}\n\n`);
          return;
        }
        if (action === "columns-3") {
          insertSnippet(textarea, `\n\n${buildColumnsSnippet(3)}\n\n`);
          return;
        }
        if (action === "image") {
          const selectedAsset = form._editorState?.selectedAsset;
          if (selectedAsset) {
            insertSelectedAsset(form, textarea, selectedAsset);
          } else {
            setEditorTab(form, "media");
            form.querySelector("[data-asset-picker]")?.click();
          }
          return;
        }
        insertSnippet(textarea, actions[action]);
      });
    });

    let timeout;
    textarea.addEventListener("input", () => {
      window.clearTimeout(timeout);
      timeout = window.setTimeout(() => refreshPreview(form), 180);
    });

    document.querySelectorAll("[data-insert-snippet]").forEach((button) => {
      button.addEventListener("click", () => {
        insertSnippet(textarea, button.dataset.insertSnippet || "");
      });
    });

    form.querySelectorAll("[data-copy-text]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await copyText(button.dataset.copyText || "");
          button.textContent = "Copiado";
          window.setTimeout(() => {
            button.textContent = "Copiar snippet";
          }, 1200);
        } catch (_error) {
          button.textContent = "No disponible";
          window.setTimeout(() => {
            button.textContent = "Copiar snippet";
          }, 1200);
        }
      });
    });

    refreshPreview(form);
  });
});
