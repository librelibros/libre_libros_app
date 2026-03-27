const actions = {
  heading: "## ",
  bold: "**texto**",
  italic: "_texto_",
  list: "- elemento",
  quote: "> cita",
  pagebreak: "\n\n<!-- pagebreak -->\n\n",
  image: "![descripcion](assets/imagen.png)",
  audio: '<audio controls src="ruta/audio.mp3"></audio>',
};

function slugifyName(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function sanitizeAssetFilename(filename) {
  const lastDot = filename.lastIndexOf(".");
  const stem = lastDot === -1 ? filename : filename.slice(0, lastDot);
  const extension = lastDot === -1 ? "" : filename.slice(lastDot).toLowerCase();
  return `${slugifyName(stem) || "asset"}${extension}`;
}

function assetSnippet(filename, mimeType = "") {
  const safeName = sanitizeAssetFilename(filename);
  if (mimeType.startsWith("image/")) {
    return `![${safeName}](assets/${safeName})`;
  }
  if (mimeType === "audio/mpeg") {
    return `<audio controls src="assets/${safeName}"></audio>`;
  }
  return `[${safeName}](assets/${safeName})`;
}

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

function initializePendingAssets(form, textarea) {
  const input = form.querySelector("[data-asset-input]");
  const dropzone = form.querySelector("[data-asset-dropzone]");
  const picker = form.querySelector("[data-asset-picker]");
  const pending = form.querySelector("[data-pending-assets]");
  const list = form.querySelector("[data-pending-assets-list]");

  if (!input || !dropzone || !picker || !pending || !list || typeof DataTransfer === "undefined") {
    return;
  }

  const transfer = new DataTransfer();

  function fileKey(file) {
    return `${file.name}:${file.size}:${file.lastModified}`;
  }

  function renderPendingAssets() {
    const files = [...transfer.files];
    pending.hidden = files.length === 0;
    list.innerHTML = "";

    files.forEach((file, index) => {
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

      const snippet = assetSnippet(file.name, file.type);
      const snippetCode = document.createElement("code");
      snippetCode.textContent = snippet;
      card.append(snippetCode);

      const actionsRow = document.createElement("div");
      actionsRow.className = "actions";

      const insertButton = document.createElement("button");
      insertButton.type = "button";
      insertButton.className = "button button-tonal";
      insertButton.textContent = "Insertar snippet";
      insertButton.addEventListener("click", () => insertSnippet(textarea, snippet));

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "button button-tonal";
      removeButton.textContent = "Quitar";
      removeButton.addEventListener("click", () => {
        const nextTransfer = new DataTransfer();
        [...transfer.files].forEach((queuedFile, queuedIndex) => {
          if (queuedIndex !== index) nextTransfer.items.add(queuedFile);
        });
        input.files = nextTransfer.files;
        transfer.items.clear();
        [...nextTransfer.files].forEach((queuedFile) => transfer.items.add(queuedFile));
        renderPendingAssets();
      });

      actionsRow.append(insertButton, removeButton);
      card.append(actionsRow);
      list.append(card);
    });
  }

  function appendFiles(files) {
    const existing = new Set([...transfer.files].map(fileKey));
    [...files].forEach((file) => {
      if (!existing.has(fileKey(file))) {
        transfer.items.add(file);
        existing.add(fileKey(file));
      }
    });
    input.files = transfer.files;
    renderPendingAssets();
  }

  picker.addEventListener("click", () => input.click());
  input.addEventListener("change", () => appendFiles(input.files));

  dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragover");
  });
  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("is-dragover");
  });
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragover");
    appendFiles(event.dataTransfer?.files || []);
  });
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initializeBookDocuments(document);

  document.querySelectorAll("[data-markdown-editor]").forEach((form) => {
    const textarea = form.querySelector("[data-editor-input]");
    if (!textarea) return;

    form.querySelectorAll("[data-editor-action]").forEach((button) => {
      button.addEventListener("click", () => {
        insertSnippet(textarea, actions[button.dataset.editorAction]);
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

    document.querySelectorAll("[data-copy-text]").forEach((button) => {
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

    initializePendingAssets(form, textarea);
    refreshPreview(form);
  });
});
