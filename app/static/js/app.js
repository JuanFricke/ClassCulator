/* Helpers comuns (Fetch + remoção de registros). */

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
    el.classList.remove("is-hidden", "is-info", "is-success", "is-danger", "is-warning");
    el.classList.add(kind);
    el.textContent = message;
  },
};

document.addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-delete-url]");
  if (!btn) return;
  event.preventDefault();
  const url = btn.dataset.deleteUrl;
  const confirmMsg = btn.dataset.confirm || "Confirma a exclusão?";
  if (!window.confirm(confirmMsg)) return;
  btn.classList.add("is-loading");
  try {
    await window.api.json(url, { method: "DELETE" });
    window.location.reload();
  } catch (err) {
    btn.classList.remove("is-loading");
    alert(`Erro: ${err.message}`);
  }
});
