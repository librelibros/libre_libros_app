// Muestra u oculta tarjetas de bienvenida según preferencia del navegador.
// Cualquier elemento con [hidden] + un botón [data-dismiss="<id>"] participa.
//
// Versión incluida en la clave para invalidar la decisión cuando cambia el
// contenido de la tarjeta (subir el sufijo y la persona vuelve a verla).
const STORAGE_VERSION = "v1";

function storageKey(cardId) {
  return `libre_libros.dismiss.${cardId}.${STORAGE_VERSION}`;
}

function safeRead(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWrite(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* private mode, quota exceeded, etc. — ignore */
  }
}

function applyInitialState() {
  document.querySelectorAll("[id][hidden].welcome-card").forEach((card) => {
    if (safeRead(storageKey(card.id)) === "1") return;
    card.hidden = false;
  });
}

function attachDismissHandlers() {
  document.querySelectorAll("[data-dismiss]").forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-dismiss");
      const card = document.getElementById(targetId);
      if (!card) return;
      card.hidden = true;
      safeWrite(storageKey(targetId), "1");
    });
  });
}

function attachImageFallbacks() {
  // Cualquier <img data-fallback="hide"> que no cargue se elimina del DOM.
  // Útil para portadas opcionales (cover.svg) cuyos repos pueden no incluirla.
  document.querySelectorAll('img[data-fallback="hide"]').forEach((img) => {
    img.addEventListener("error", () => img.remove(), { once: true });
    if (img.complete && img.naturalWidth === 0) img.remove();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applyInitialState();
  attachDismissHandlers();
  attachImageFallbacks();
});
