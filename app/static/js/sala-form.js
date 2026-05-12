const form = document.getElementById("sala-form");
const feedback = document.getElementById("sala-feedback");

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const payload = {
    nome: data.get("nome"),
    tipo: data.get("tipo"),
    capacidade: parseInt(data.get("capacidade"), 10),
  };
  const id = form.dataset.id;
  const url = id ? `/api/v1/salas/${id}` : "/api/v1/salas";
  const method = id ? "PATCH" : "POST";
  try {
    const result = await window.api.json(url, {
      method,
      body: JSON.stringify(payload),
    });
    window.api.feedback(feedback, "Sala salva.", "is-success");
    if (!id && result?.id) {
      setTimeout(() => (window.location.href = `/salas/${result.id}`), 600);
    }
  } catch (err) {
    window.api.feedback(feedback, err.message, "is-danger");
  }
});
