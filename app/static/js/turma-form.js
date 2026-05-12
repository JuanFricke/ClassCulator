const form = document.getElementById("turma-form");
const feedback = document.getElementById("turma-feedback");

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const payload = {
    identificador: data.get("identificador"),
    semestre: data.get("semestre"),
    qtd_alunos: parseInt(data.get("qtd_alunos"), 10),
  };
  const id = form.dataset.id;
  const url = id ? `/api/v1/turmas/${id}` : "/api/v1/turmas";
  const method = id ? "PATCH" : "POST";
  try {
    const result = await window.api.json(url, {
      method,
      body: JSON.stringify(payload),
    });
    window.api.feedback(feedback, "Turma salva.", "is-success");
    if (!id && result?.id) {
      setTimeout(() => (window.location.href = `/turmas/${result.id}`), 600);
    }
  } catch (err) {
    window.api.feedback(feedback, err.message, "is-danger");
  }
});

// --- Currículo dinâmico ---------------------------------------------------- //
const curriculoForm = document.getElementById("curriculo-form");
const curriculoFeedback = document.getElementById("curriculo-feedback");
const tableBody = document.querySelector("#curriculo-table tbody");
const rowTemplate = document.getElementById("curriculo-row-template");
const addBtn = document.getElementById("curriculo-add");

function bindRow(row) {
  row.querySelector(".js-remove-row")?.addEventListener("click", () => row.remove());
}

document.querySelectorAll("#curriculo-table tbody tr").forEach(bindRow);

addBtn?.addEventListener("click", () => {
  const fragment = rowTemplate.content.cloneNode(true);
  const row = fragment.querySelector("tr");
  bindRow(row);
  tableBody.appendChild(row);
});

curriculoForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const turmaId = curriculoForm.dataset.turmaId;
  const items = Array.from(tableBody.querySelectorAll("tr")).map((tr) => ({
    disciplina_id: parseInt(tr.querySelector("select[name=disciplina_id]").value, 10),
    professor_id: parseInt(tr.querySelector("select[name=professor_id]").value, 10),
  }));
  try {
    await window.api.json(`/api/v1/turmas/${turmaId}/curriculo`, {
      method: "PUT",
      body: JSON.stringify({ items }),
    });
    window.api.feedback(curriculoFeedback, "Currículo salvo.", "is-success");
  } catch (err) {
    window.api.feedback(curriculoFeedback, err.message, "is-danger");
  }
});
