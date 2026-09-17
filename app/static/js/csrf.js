// Explicit opt-in for app requests; never patch the browser's global fetch.
window.LibreLibrosCSRF = {
  options(url, options = {}) {
    const target = new URL(url, window.location.href);
    if (target.origin !== window.location.origin || target.username || target.password) {
      throw new Error("No se permite enviar formularios a un origen externo.");
    }
    const headers = new Headers(options.headers);
    const method = (options.method || "GET").toUpperCase();
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      const token = document.querySelector('meta[name="csrf-token"]')?.content;
      if (!token) throw new Error("Sesión no disponible. Recarga la página antes de continuar.");
      headers.set("X-CSRF-Token", token);
    }
    // Also reject cross-origin redirects: neither headers nor form tokens may
    // follow a redirected POST to an external destination.
    return { ...options, headers, credentials: "same-origin", mode: "same-origin" };
  },
};
