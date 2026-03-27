const actions = {
  heading: "## ",
  bold: "**texto**",
  italic: "_texto_",
  list: "- elemento",
  quote: "> cita",
  image: "![descripcion](ruta/imagen.png)",
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
  const response = await fetch("/books/preview", { method: "POST", body });
  preview.innerHTML = await response.text();
}

document.addEventListener("DOMContentLoaded", () => {
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

