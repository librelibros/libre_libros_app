const actions = {
  heading: "## ",
  bold: "**texto**",
  italic: "_texto_",
  list: "- elemento",
  quote: "> cita",
  pagebreak: "\n\n<!-- pagebreak -->\n\n",
  audio: '<audio controls src="assets/audio.mp3"></audio>',
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
    hint.textContent = "La imagen se insertara con clases de maquetacion para moverla a izquierda, derecha o centrarla y ajustar su ancho.";
  } else {
    altInput.value = "";
    altInput.disabled = true;
    alignInput.disabled = true;
    sizeInput.disabled = true;
    hint.textContent = "Los audios se insertan como bloque de reproduccion. Las opciones de posicion y tamano no se aplican.";
  }
}

function setSelectedAsset(form, asset) {
  form._editorState.selectedAsset = asset;
  renderSelectedAsset(form);
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

function renderPendingAssets(form, textarea) {
  const state = form._editorState;
  const pending = form.querySelector("[data-pending-assets]");
  const list = form.querySelector("[data-pending-assets-list]");
  if (!pending || !list) return;

  const files = [...state.transfer.files];
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
      image.src = URL.createObjectURL(file);
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
    selectedAsset: null,
  };

  function handleFileDrop(files) {
    appendFilesToEditor(form, textarea, files);
  }

  picker?.addEventListener("click", () => input?.click());
  input?.addEventListener("change", () => {
    appendFilesToEditor(form, textarea, input.files);
  });

  [dropzone, surface, textarea].forEach((target) => {
    target?.addEventListener("dragover", (event) => {
      event.preventDefault();
      surface?.classList.add("is-dragover");
      dropzone?.classList.add("is-dragover");
    });
    target?.addEventListener("dragleave", () => {
      surface?.classList.remove("is-dragover");
      dropzone?.classList.remove("is-dragover");
    });
    target?.addEventListener("drop", (event) => {
      event.preventDefault();
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

  form.querySelectorAll("[data-select-asset]").forEach((button) => {
    button.addEventListener("click", () => {
      setSelectedAsset(form, assetFromButton(button));
      form.querySelector("[data-media-studio]")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  });

  form.querySelectorAll("[data-insert-asset]").forEach((button) => {
    button.addEventListener("click", () => {
      const asset = assetFromButton(button);
      setSelectedAsset(form, asset);
      insertSelectedAsset(form, textarea, asset);
    });
  });

  renderSelectedAsset(form);
  renderPendingAssets(form, textarea);
}

document.addEventListener("DOMContentLoaded", () => {
  initializeBookDocuments(document);

  document.querySelectorAll("[data-markdown-editor]").forEach((form) => {
    const textarea = form.querySelector("[data-editor-input]");
    if (!textarea) return;

    initializeMediaStudio(form, textarea);

    form.querySelectorAll("[data-editor-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.dataset.editorAction;
        if (action === "image") {
          const selectedAsset = form._editorState?.selectedAsset;
          if (selectedAsset) {
            insertSelectedAsset(form, textarea, selectedAsset);
          } else {
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
