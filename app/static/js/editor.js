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

function insertSnippet(textarea, snippet) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const before = textarea.value.slice(0, start);
  const after = textarea.value.slice(end);
  textarea.value = `${before}${snippet}${after}`;
  textarea.selectionStart = textarea.selectionEnd = start + snippet.length;
  textarea.dispatchEvent(new Event("input"));
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
    refreshPreview(form);
  });
});
