// Re-poll quando ainda está em execução, redireciona ao concluir.
(async () => {
  const status = document.querySelector(".tag.is-large")?.textContent?.trim();
  if (!["pending", "running"].includes(status)) return;

  const path = window.location.pathname.split("/");
  const id = parseInt(path[path.length - 1], 10);
  if (Number.isNaN(id)) return;

  for (let i = 0; i < 60; i += 1) {
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
