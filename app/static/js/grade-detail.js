/* Filtro por turma + auto-refresh enquanto a grade está em execução. */

(function turmaFilter() {
  const select = document.getElementById("turma-filter");
  if (!select) return;
  const blocks = document.querySelectorAll(".turma-block");
  select.addEventListener("change", () => {
    const value = select.value;
    blocks.forEach((block) => {
      const show = value === "__all__" || block.dataset.turmaId === value;
      block.classList.toggle("is-hidden", !show);
    });
  });
})();

(async function autoRefresh() {
  // Identifica o status mostrado em forma textual (Aguardando / Em andamento).
  const statusEl = document.querySelector(".subtitle .tag");
  const label = statusEl?.textContent?.trim() ?? "";
  if (!/(Aguardando|Em andamento)/i.test(label)) return;

  const path = window.location.pathname.split("/");
  const id = parseInt(path[path.length - 1], 10);
  if (Number.isNaN(id)) return;

  for (let i = 0; i < 90; i += 1) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const data = await window.api.json(`/api/v1/grade/status/${id}`);
      if (data.status === "done" || data.status === "failed") {
        window.location.reload();
        return;
      }
    } catch (_) {
      return;
    }
  }
})();
