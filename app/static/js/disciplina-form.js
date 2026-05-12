const form = document.getElementById("disciplina-form");
const feedback = document.getElementById("disciplina-feedback");

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const payload = {
    nome: data.get("nome"),
    area: data.get("area"),
    carga_semanal: parseInt(data.get("carga_semanal"), 10),
    requer_lab: data.get("requer_lab") === "on",
    eh_teorica: data.get("eh_teorica") === "on",
  };
  const id = form.dataset.id;
  const url = id ? `/api/v1/disciplinas/${id}` : "/api/v1/disciplinas";
  const method = id ? "PATCH" : "POST";
  try {
    const result = await window.api.json(url, {
      method,
      body: JSON.stringify(payload),
    });
    window.api.feedback(feedback, "Disciplina salva.", "is-success");
    if (!id && result?.id) {
      setTimeout(() => (window.location.href = `/disciplinas/${result.id}`), 600);
    }
  } catch (err) {
    window.api.feedback(feedback, err.message, "is-danger");
  }
});
