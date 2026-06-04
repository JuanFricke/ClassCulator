/* Modo de edição manual da grade.
 *
 * Permite (apenas quando a grade está "done"):
 *  - arrastar e soltar uma matéria para outro horário da MESMA turma (mover/trocar);
 *  - clicar numa célula para editar disciplina + professor (+ sala) ou esvaziá-la;
 *  - salvar o resultado como uma NOVA grade via POST /api/v1/grade/{id}/editar.
 *
 * Não roda otimização; o backend bloqueia apenas conflitos rígidos de horário.
 */

(function gradeManualEdit() {
  const dataEl = document.getElementById("grade-edit-data");
  const toggle = document.getElementById("grade-edit-toggle");
  if (!dataEl || !toggle) return;

  let data;
  try {
    data = JSON.parse(dataEl.textContent || "{}");
  } catch (_) {
    return;
  }

  const gradeId = data.gradeId;
  const discById = new Map((data.disciplinas || []).map((d) => [String(d.id), d]));
  const profById = new Map((data.professores || []).map((p) => [String(p.id), p]));
  const salaById = new Map((data.salas || []).map((s) => [String(s.id), s]));
  const profsPorDisc = data.professoresPorDisciplina || {};

  const bar = document.getElementById("grade-edit-bar");
  const feedback = document.getElementById("grade-edit-feedback");
  const orientationToggle = document.getElementById("grade-orientation-toggle");
  const saveBtn = document.getElementById("grade-edit-save");
  const cancelBtn = document.getElementById("grade-edit-cancel");

  // Editor (modal)
  const modal = document.getElementById("cell-editor-modal");
  const selDisc = document.getElementById("cell-editor-disciplina");
  const selProf = document.getElementById("cell-editor-professor");
  const selSala = document.getElementById("cell-editor-sala");
  const editorError = document.getElementById("cell-editor-error");
  const btnApply = document.getElementById("cell-editor-apply");
  const btnClear = document.getElementById("cell-editor-clear");
  const btnCancel = document.getElementById("cell-editor-cancel");
  const btnClose = document.getElementById("cell-editor-close");

  let editing = false;
  let dragSource = null;
  let activeCell = null;

  const editableCells = () =>
    Array.from(document.querySelectorAll(".grade-cell")).filter(
      (td) => !td.classList.contains("grade-cell--off"),
    );

  const isFilled = (td) => Boolean(td.dataset.disciplinaId);

  function renderCell(td) {
    const discId = td.dataset.disciplinaId;
    if (!discId) {
      td.dataset.area = "";
      td.removeAttribute("draggable");
      td.innerHTML = '<span class="has-text-grey-light">—</span>';
      return;
    }
    const disc = discById.get(String(discId));
    const prof = profById.get(String(td.dataset.professorId));
    const sala = td.dataset.salaId ? salaById.get(String(td.dataset.salaId)) : null;
    td.dataset.area = disc ? disc.area : "";
    td.setAttribute("draggable", "true");
    const parts = [];
    parts.push(`<strong>${disc ? disc.nome : "?"}</strong>`);
    parts.push(`<span>${prof ? prof.nome : "?"}</span>`);
    if (sala) parts.push(`<span class="cell-room">${sala.nome}</span>`);
    td.innerHTML = parts.join("");
  }

  function setCellData(td, discId, profId, salaId) {
    td.dataset.disciplinaId = discId ? String(discId) : "";
    td.dataset.professorId = profId ? String(profId) : "";
    td.dataset.salaId = salaId ? String(salaId) : "";
    renderCell(td);
  }

  function clearCell(td) {
    setCellData(td, "", "", "");
  }

  // --- Drag and drop (restrito à mesma turma) ----------------------------- //
  function onDragStart(event) {
    const td = event.target.closest(".grade-cell");
    if (!editing || !td || !isFilled(td)) {
      event.preventDefault();
      return;
    }
    dragSource = td;
    td.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
    try {
      event.dataTransfer.setData("text/plain", td.dataset.slot || "");
    } catch (_) {}
  }

  function sameTurma(a, b) {
    return a && b && a.dataset.turmaId && a.dataset.turmaId === b.dataset.turmaId;
  }

  function onDragOver(event) {
    if (!editing || !dragSource) return;
    const td = event.target.closest(".grade-cell");
    if (!td || td.classList.contains("grade-cell--off") || !sameTurma(dragSource, td)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    td.classList.add("is-drop-target");
  }

  function onDragLeave(event) {
    const td = event.target.closest(".grade-cell");
    if (td) td.classList.remove("is-drop-target");
  }

  function onDrop(event) {
    if (!editing || !dragSource) return;
    const target = event.target.closest(".grade-cell");
    if (!target || target.classList.contains("grade-cell--off") || !sameTurma(dragSource, target)) {
      return;
    }
    event.preventDefault();
    target.classList.remove("is-drop-target");
    if (target === dragSource) return;

    // Troca o conteúdo (disciplina/professor/sala) entre origem e destino.
    const src = {
      disc: dragSource.dataset.disciplinaId,
      prof: dragSource.dataset.professorId,
      sala: dragSource.dataset.salaId,
    };
    const dst = {
      disc: target.dataset.disciplinaId,
      prof: target.dataset.professorId,
      sala: target.dataset.salaId,
    };
    setCellData(dragSource, dst.disc, dst.prof, dst.sala);
    setCellData(target, src.disc, src.prof, src.sala);
  }

  function onDragEnd() {
    if (dragSource) dragSource.classList.remove("is-dragging");
    document
      .querySelectorAll(".grade-cell.is-drop-target")
      .forEach((td) => td.classList.remove("is-drop-target"));
    dragSource = null;
  }

  // --- Editor de célula --------------------------------------------------- //
  function populateProfessores(discId, selectedProfId) {
    selProf.innerHTML = "";
    const allowed = (profsPorDisc[String(discId)] || []).map(String);
    if (!discId) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "—";
      selProf.appendChild(opt);
      selProf.disabled = true;
      return;
    }
    selProf.disabled = false;
    const pool = allowed.length ? allowed : Array.from(profById.keys());
    pool.forEach((pid) => {
      const prof = profById.get(String(pid));
      if (!prof) return;
      const opt = document.createElement("option");
      opt.value = String(pid);
      opt.textContent = prof.nome;
      selProf.appendChild(opt);
    });
    if (selectedProfId && pool.includes(String(selectedProfId))) {
      selProf.value = String(selectedProfId);
    } else if (selProf.options.length) {
      selProf.selectedIndex = 0;
    }
  }

  function buildEditorOptions() {
    // Disciplinas
    selDisc.innerHTML = '<option value="">— Vazio —</option>';
    (data.disciplinas || []).forEach((d) => {
      const opt = document.createElement("option");
      opt.value = String(d.id);
      opt.textContent = d.nome;
      selDisc.appendChild(opt);
    });
    // Salas
    selSala.innerHTML = '<option value="">— Sem sala —</option>';
    (data.salas || []).forEach((s) => {
      const opt = document.createElement("option");
      opt.value = String(s.id);
      opt.textContent = s.nome;
      selSala.appendChild(opt);
    });
  }

  function openEditor(td) {
    activeCell = td;
    editorError.classList.add("is-hidden");
    editorError.textContent = "";
    selDisc.value = td.dataset.disciplinaId || "";
    populateProfessores(td.dataset.disciplinaId, td.dataset.professorId);
    selSala.value = td.dataset.salaId || "";
    modal.classList.add("is-active");
  }

  function closeEditor() {
    modal.classList.remove("is-active");
    activeCell = null;
  }

  selDisc.addEventListener("change", () => {
    populateProfessores(selDisc.value, null);
  });

  btnApply.addEventListener("click", () => {
    if (!activeCell) return;
    const discId = selDisc.value;
    if (!discId) {
      clearCell(activeCell);
      closeEditor();
      return;
    }
    const profId = selProf.value;
    if (!profId) {
      editorError.textContent = "Escolha um professor para a disciplina selecionada.";
      editorError.classList.remove("is-hidden");
      return;
    }
    setCellData(activeCell, discId, profId, selSala.value || "");
    closeEditor();
  });

  btnClear.addEventListener("click", () => {
    if (!activeCell) return;
    clearCell(activeCell);
    closeEditor();
  });

  [btnCancel, btnClose].forEach((b) =>
    b && b.addEventListener("click", closeEditor),
  );
  modal.querySelector(".modal-background")?.addEventListener("click", closeEditor);

  function onCellClick(event) {
    if (!editing) return;
    const td = event.target.closest(".grade-cell");
    if (!td || td.classList.contains("grade-cell--off")) return;
    openEditor(td);
  }

  // --- Salvar ------------------------------------------------------------- //
  function coletarAlocacoes() {
    const items = [];
    editableCells().forEach((td) => {
      if (!isFilled(td)) return;
      items.push({
        turma_id: parseInt(td.dataset.turmaId, 10),
        disciplina_id: parseInt(td.dataset.disciplinaId, 10),
        professor_id: parseInt(td.dataset.professorId, 10),
        sala_id: td.dataset.salaId ? parseInt(td.dataset.salaId, 10) : null,
        dia: parseInt(td.dataset.dia, 10),
        slot: parseInt(td.dataset.slot, 10),
      });
    });
    return items;
  }

  function showFeedback(message, kind = "is-danger") {
    if (!feedback) return;
    feedback.classList.remove("is-hidden");
    feedback.classList.toggle("is-danger", kind === "is-danger");
    feedback.classList.toggle("is-success", kind === "is-success");
    feedback.innerHTML = message;
  }

  async function salvar() {
    if (!feedback) return;
    feedback.classList.add("is-hidden");
    saveBtn.classList.add("is-loading");
    const payload = { alocacoes: coletarAlocacoes() };
    try {
      const res = await fetch(`/api/v1/grade/${gradeId}/editar`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.status === 201) {
        const body = await res.json();
        window.location.href = `/grade/${body.id}`;
        return;
      }
      const text = await res.text();
      let detail = text;
      try {
        detail = JSON.parse(text).detail ?? text;
      } catch (_) {}
      if (detail && typeof detail === "object" && Array.isArray(detail.conflitos)) {
        const lista = detail.conflitos.map((c) => `<li>${c}</li>`).join("");
        showFeedback(
          `<strong>${detail.message || "Conflitos de horário."}</strong><ul>${lista}</ul>`,
        );
      } else {
        showFeedback(typeof detail === "string" ? detail : `HTTP ${res.status}`);
      }
    } catch (err) {
      showFeedback(err.message || "Falha ao salvar a grade editada.");
    } finally {
      saveBtn.classList.remove("is-loading");
    }
  }

  // --- Alternância do modo de edição -------------------------------------- //
  function enterEditMode() {
    editing = true;
    document.body.classList.add("grade-editing");
    bar.classList.remove("is-hidden");
    toggle.setAttribute("aria-pressed", "true");
    toggle.classList.add("is-warning");
    toggle.classList.remove("is-light");
    if (orientationToggle) orientationToggle.disabled = true;
    editableCells().forEach((td) => {
      if (isFilled(td)) td.setAttribute("draggable", "true");
    });
  }

  function exitEditMode() {
    // Recarrega para descartar as edições não salvas e restaurar o estado limpo.
    window.location.reload();
  }

  toggle.addEventListener("click", () => {
    if (editing) {
      exitEditMode();
    } else {
      enterEditMode();
    }
  });

  cancelBtn?.addEventListener("click", exitEditMode);
  saveBtn?.addEventListener("click", salvar);

  buildEditorOptions();

  // Listeners de drag/drop e clique (delegados; só agem em modo de edição).
  document.addEventListener("dragstart", onDragStart);
  document.addEventListener("dragover", onDragOver);
  document.addEventListener("dragleave", onDragLeave);
  document.addEventListener("drop", onDrop);
  document.addEventListener("dragend", onDragEnd);
  document.addEventListener("click", onCellClick);
})();
