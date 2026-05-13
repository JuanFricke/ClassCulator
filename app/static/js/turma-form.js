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
    window.api.feedback(feedback, "Turma salva com sucesso.", "is-success");
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
const cargaBar = document.getElementById("carga-bar");
const cargaFill = cargaBar?.querySelector(".carga-fill");
const cargaLabel = document.getElementById("carga-label");
const cargaAtual = document.getElementById("carga-atual");
const cargaStatus = document.getElementById("carga-status");
const cargaAlvo = parseInt(curriculoForm?.dataset.cargaAlvo || "30", 10);

function recalcularCarga() {
  if (!tableBody) return;
  let total = 0;
  tableBody.querySelectorAll("tr").forEach((tr) => {
    const select = tr.querySelector("select[name=disciplina_id]");
    if (!select) return;
    const opt = select.options[select.selectedIndex];
    total += parseInt(opt?.dataset.carga || "0", 10);
  });
  const pct = Math.min(100, Math.round((total / cargaAlvo) * 100));
  if (cargaFill) cargaFill.style.width = `${pct}%`;
  if (cargaLabel) cargaLabel.textContent = `${total} / ${cargaAlvo}`;
  if (cargaAtual) cargaAtual.textContent = total;
  if (cargaBar) {
    cargaBar.classList.toggle("is-complete", total === cargaAlvo);
    cargaBar.classList.toggle("is-incomplete", total > 0 && total < cargaAlvo);
    cargaBar.classList.toggle("is-over", total > cargaAlvo);
  }
  if (cargaStatus) {
    if (total === cargaAlvo) {
      cargaStatus.innerHTML = `<strong class="has-text-success">${total} de ${cargaAlvo} aulas ✓</strong>`;
    } else if (total > cargaAlvo) {
      cargaStatus.innerHTML = `<strong class="has-text-danger">${total} de ${cargaAlvo} aulas (excesso de ${total - cargaAlvo})</strong>`;
    } else {
      const falta = cargaAlvo - total;
      cargaStatus.innerHTML = `<span class="has-text-warning-dark"><strong>${total}</strong> de ${cargaAlvo} aulas (faltam ${falta})</span>`;
    }
  }
}

function bindRow(row) {
  row.querySelector(".js-remove-row")?.addEventListener("click", () => {
    row.remove();
    recalcularCarga();
  });
  row.querySelector("select[name=disciplina_id]")?.addEventListener("change", recalcularCarga);
}

document.querySelectorAll("#curriculo-table tbody tr").forEach(bindRow);
recalcularCarga();

addBtn?.addEventListener("click", () => {
  const fragment = rowTemplate.content.cloneNode(true);
  const row = fragment.querySelector("tr");
  bindRow(row);
  tableBody.appendChild(row);
  recalcularCarga();
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
    window.api.feedback(curriculoFeedback, "Currículo salvo com sucesso.", "is-success");
    recalcularCarga();
  } catch (err) {
    window.api.feedback(curriculoFeedback, err.message, "is-danger");
  }
});
