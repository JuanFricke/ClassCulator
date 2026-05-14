const form = document.getElementById("turma-form");
const feedback = document.getElementById("turma-feedback");
const identificadorInput = document.getElementById("turma-identificador");
const ensinoSelect = document.getElementById("turma-ensino");
const slotInputs = Array.from(document.querySelectorAll(".js-slot-input"));
const slotsTotalDisplay = document.getElementById("slots-total-display");

function inferEnsinoFromTurma(identificador) {
  const upper = (identificador || "").trim().toUpperCase();
  if (upper.startsWith("EF")) return "fundamental";
  if (upper.startsWith("EM")) return "medio";
  return "ambos";
}

identificadorInput?.addEventListener("input", () => {
  if (!ensinoSelect) return;
  ensinoSelect.value = inferEnsinoFromTurma(identificadorInput.value);
});

function readSlotsPorDia() {
  if (slotInputs.length !== 5) return null;
  const valores = new Array(5).fill(0);
  for (const input of slotInputs) {
    const dia = parseInt(input.dataset.dia, 10);
    const raw = parseInt(input.value, 10);
    valores[dia] = Number.isFinite(raw) ? Math.max(0, raw) : 0;
  }
  return valores;
}

function updateSlotsTotalDisplay() {
  if (!slotsTotalDisplay) return;
  const valores = readSlotsPorDia() || [];
  slotsTotalDisplay.textContent = valores.reduce((a, b) => a + b, 0);
}

slotInputs.forEach((input) => {
  input.addEventListener("input", updateSlotsTotalDisplay);
});

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const slotsPorDia = readSlotsPorDia();
  const payload = {
    identificador: data.get("identificador"),
    ensino: inferEnsinoFromTurma(data.get("identificador")),
    semestre: data.get("semestre"),
    qtd_alunos: parseInt(data.get("qtd_alunos"), 10),
  };
  if (slotsPorDia) {
    payload.slots_por_dia = slotsPorDia;
  }
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
      return;
    }
    // Edição: propaga o novo carga_alvo para todos os displays sem reload.
    const novoAlvo = Array.isArray(result?.slots_por_dia)
      ? result.slots_por_dia.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0)
      : (slotsPorDia ? slotsPorDia.reduce((a, b) => a + b, 0) : null);
    if (novoAlvo !== null) {
      setCargaAlvo(novoAlvo);
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
const cargaAlvoLabel = document.getElementById("carga-alvo-label");
const cargaAlvoHelp = document.getElementById("carga-alvo-help");
const cargaAlvoSubtitle = document.getElementById("carga-alvo-subtitle");
let cargaAlvo = parseInt(curriculoForm?.dataset.cargaAlvo || "30", 10);

function setCargaAlvo(novoValor) {
  const valor = parseInt(novoValor, 10);
  if (!Number.isFinite(valor) || valor < 0) return;
  cargaAlvo = valor;
  if (curriculoForm) curriculoForm.dataset.cargaAlvo = String(valor);
  if (cargaAlvoLabel) cargaAlvoLabel.textContent = String(valor);
  if (cargaAlvoHelp) cargaAlvoHelp.textContent = String(valor);
  if (cargaAlvoSubtitle) cargaAlvoSubtitle.textContent = String(valor);
  recalcularCarga();
}

function parseAllowedProfessorIds(disciplinaSelect) {
  const opt = disciplinaSelect?.options[disciplinaSelect.selectedIndex];
  const raw = opt?.dataset.professores || "";
  return raw
    .split(",")
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

function syncProfessorOptions(row) {
  const disciplinaSelect = row.querySelector("select[name=disciplina_id]");
  const professorSelect = row.querySelector("select[name=professor_id]");
  if (!disciplinaSelect || !professorSelect) return;

  const allowedProfessorIds = new Set(parseAllowedProfessorIds(disciplinaSelect));
  const options = Array.from(professorSelect.options);

  if (allowedProfessorIds.size === 0) {
    options.forEach((option) => {
      option.hidden = true;
      option.disabled = true;
    });
    professorSelect.disabled = true;
    professorSelect.value = "";
    return;
  }

  professorSelect.disabled = false;
  options.forEach((option) => {
    const isAllowed = allowedProfessorIds.has(option.value);
    option.hidden = !isAllowed;
    option.disabled = !isAllowed;
  });

  if (!allowedProfessorIds.has(professorSelect.value)) {
    const firstAllowed = options.find((option) => allowedProfessorIds.has(option.value));
    professorSelect.value = firstAllowed ? firstAllowed.value : "";
  }
}

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
  row.querySelector("select[name=disciplina_id]")?.addEventListener("change", () => {
    syncProfessorOptions(row);
    recalcularCarga();
  });
  syncProfessorOptions(row);
}

function disciplinasJaUsadas() {
  const ids = new Set();
  tableBody?.querySelectorAll("select[name=disciplina_id]").forEach((sel) => {
    if (sel.value) ids.add(sel.value);
  });
  return ids;
}

function escolherDisciplinaInedita(select) {
  if (!select) return;
  const usadas = disciplinasJaUsadas();
  const opcoes = Array.from(select.options);
  const inedita = opcoes.find(
    (opt) => opt.value && !usadas.has(opt.value) && !opt.disabled,
  );
  if (inedita) select.value = inedita.value;
}

document.querySelectorAll("#curriculo-table tbody tr").forEach(bindRow);
recalcularCarga();

addBtn?.addEventListener("click", () => {
  const fragment = rowTemplate.content.cloneNode(true);
  const row = fragment.querySelector("tr");
  const disciplinaSelect = row.querySelector("select[name=disciplina_id]");
  escolherDisciplinaInedita(disciplinaSelect);
  bindRow(row);
  tableBody.appendChild(row);
  recalcularCarga();
});

curriculoForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const turmaId = curriculoForm.dataset.turmaId;
  const items = Array.from(tableBody.querySelectorAll("tr")).map((tr) => {
    const disciplinaId = parseInt(tr.querySelector("select[name=disciplina_id]").value, 10);
    const professorValue = tr.querySelector("select[name=professor_id]").value;
    const professorId = parseInt(professorValue, 10);
    return {
      disciplina_id: disciplinaId,
      professor_id: professorId,
    };
  });

  if (items.some((item) => Number.isNaN(item.disciplina_id) || Number.isNaN(item.professor_id))) {
    window.api.feedback(
      curriculoFeedback,
      "Cada disciplina deve ter um professor habilitado para ela antes de salvar.",
      "is-danger",
    );
    return;
  }
  const disciplinaIds = items.map((it) => it.disciplina_id);
  const duplicadas = disciplinaIds.filter(
    (id, idx) => disciplinaIds.indexOf(id) !== idx,
  );
  if (duplicadas.length > 0) {
    const nomes = new Set();
    tableBody.querySelectorAll("select[name=disciplina_id]").forEach((sel) => {
      if (!duplicadas.includes(parseInt(sel.value, 10))) return;
      const opt = sel.options[sel.selectedIndex];
      const texto = (opt?.textContent || "").trim();
      if (texto) nomes.add(texto.split(" (")[0]);
    });
    const rotulo = Array.from(nomes).join(", ") || "(verifique a lista)";
    window.api.feedback(
      curriculoFeedback,
      `Disciplinas repetidas no currículo: ${rotulo}. Cada disciplina deve aparecer apenas uma vez por turma.`,
      "is-danger",
    );
    return;
  }
  let cargaTotal = 0;
  tableBody.querySelectorAll("tr").forEach((tr) => {
    const disciplinaSelect = tr.querySelector("select[name=disciplina_id]");
    if (!disciplinaSelect) return;
    const opt = disciplinaSelect.options[disciplinaSelect.selectedIndex];
    cargaTotal += parseInt(opt?.dataset.carga || "0", 10);
  });
  if (cargaTotal > cargaAlvo) {
    window.api.feedback(
      curriculoFeedback,
      `Carga total acima do máximo: ${cargaTotal}/${cargaAlvo}. Remova disciplinas antes de salvar.`,
      "is-danger",
    );
    return;
  }

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
