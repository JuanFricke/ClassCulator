const form = document.getElementById("professor-form");
const feedback = document.getElementById("professor-feedback");

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const disciplinaIds = data.getAll("disciplina_ids").map((v) => parseInt(v, 10));
  const payload = {
    nome: data.get("nome"),
    email: data.get("email") || null,
    disciplina_ids: disciplinaIds,
  };
  const id = form.dataset.id;
  const url = id ? `/api/v1/professores/${id}` : "/api/v1/professores";
  const method = id ? "PATCH" : "POST";
  try {
    const result = await window.api.json(url, {
      method,
      body: JSON.stringify(payload),
    });
    window.api.feedback(feedback, "Professor salvo.", "is-success");
    if (!id && result?.id) {
      setTimeout(() => (window.location.href = `/professores/${result.id}`), 600);
    }
  } catch (err) {
    window.api.feedback(feedback, err.message, "is-danger");
  }
});

const dispForm = document.getElementById("disponibilidade-form");
const dispFeedback = document.getElementById("disp-feedback");

dispForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const profId = dispForm.dataset.profId;
  const items = Array.from(
    dispForm.querySelectorAll("input[type=checkbox][data-dia]")
  ).map((input) => ({
    dia: parseInt(input.dataset.dia, 10),
    slot: parseInt(input.dataset.slot, 10),
    disponivel: input.checked,
  }));
  try {
    await window.api.json(`/api/v1/professores/${profId}/disponibilidade`, {
      method: "PUT",
      body: JSON.stringify({ items }),
    });
    window.api.feedback(dispFeedback, "Disponibilidade salva.", "is-success");
  } catch (err) {
    window.api.feedback(dispFeedback, err.message, "is-danger");
  }
});
