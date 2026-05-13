/* Helpers comuns: Fetch, feedback, confirmação customizada. */

window.api = {
  async json(url, options = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...options,
    });
    if (!res.ok) {
      const text = await res.text();
      let message = text;
      try {
        message = JSON.parse(text).detail ?? text;
      } catch (_) {}
      throw new Error(message || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return res.json();
  },
  feedback(el, message, kind = "is-info") {
    if (!el) return;
    el.classList.remove(
      "is-hidden", "is-info", "is-success", "is-danger", "is-warning",
    );
    el.classList.add("cc-feedback", kind);
    el.textContent = message;
    if (kind === "is-success") {
      setTimeout(() => el.classList.add("is-hidden"), 4000);
    }
  },
};

function initNavbarBurger() {
  const burger = document.querySelector("[data-navbar-burger]");
  if (!burger) return;
  const targetId = burger.dataset.target;
  const menu = targetId ? document.getElementById(targetId) : null;
  if (!menu) return;
  burger.addEventListener("click", () => {
    const isActive = burger.classList.toggle("is-active");
    menu.classList.toggle("is-active", isActive);
    burger.setAttribute("aria-expanded", isActive ? "true" : "false");
  });
}

// --- modal de confirmação em markup Bulma --- //
function confirmDialog({ title = "Confirmar", message, confirmLabel = "Confirmar", confirmKind = "is-danger" }) {
  return new Promise((resolve) => {
    const root = document.getElementById("cc-modal-root") || document.body;
    const wrap = document.createElement("div");
    wrap.className = "modal is-active";
    wrap.innerHTML = `
      <div class="modal-background" data-cancel></div>
      <div class="modal-card" role="dialog" aria-modal="true" aria-label="${title}">
        <header class="modal-card-head">
          <p class="modal-card-title is-size-5">${title}</p>
          <button class="delete" aria-label="close" data-cancel></button>
        </header>
        <section class="modal-card-body">
          <p class="mb-0">${message}</p>
        </section>
        <footer class="modal-card-foot is-justify-content-flex-end">
          <button class="button" data-cancel>Cancelar</button>
          <button class="button ${confirmKind}" data-confirm>${confirmLabel}</button>
        </footer>
      </div>
      <button class="modal-close is-large" aria-label="close" data-cancel></button>
    `;
    const close = (value) => {
      wrap.remove();
      resolve(value);
    };
    wrap.querySelectorAll("[data-cancel]").forEach((el) => {
      el.addEventListener("click", () => close(false));
    });
    wrap.querySelector("[data-confirm]").addEventListener("click", () => close(true));
    document.addEventListener(
      "keydown",
      (e) => {
        if (e.key === "Escape") close(false);
      },
      { once: true },
    );
    root.appendChild(wrap);
    wrap.querySelector("[data-confirm]").focus();
  });
}
window.confirmDialog = confirmDialog;

document.addEventListener("DOMContentLoaded", () => {
  initNavbarBurger();
});

document.addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-delete-url]");
  if (!btn) return;
  event.preventDefault();
  const url = btn.dataset.deleteUrl;
  const message = btn.dataset.confirm || "Tem certeza que deseja excluir este registro?";
  const ok = await confirmDialog({
    title: "Confirmar exclusão",
    message,
    confirmLabel: "Sim, excluir",
    confirmKind: "is-danger",
  });
  if (!ok) return;
  btn.classList.add("is-loading");
  try {
    await window.api.json(url, { method: "DELETE" });
    window.location.reload();
  } catch (err) {
    btn.classList.remove("is-loading");
    await confirmDialog({
      title: "Erro",
      message: err.message,
      confirmLabel: "Ok",
      confirmKind: "is-link",
    });
  }
});
