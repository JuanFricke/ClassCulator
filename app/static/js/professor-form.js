function initProfessorForm() {
  const form = document.getElementById("professor-form");
  const feedback = document.getElementById("professor-feedback");
  const formActions = document.getElementById("professor-form-actions");
  const submitBtn = document.getElementById("professor-form-submit");
  const senhaTempPanel = document.getElementById("professor-senha-temp");
  const senhaTempInput = document.getElementById("professor-senha-temp-valor");
  const senhaTempCopiar = document.getElementById("professor-senha-temp-copiar");
  const senhaTempCopiado = document.getElementById("professor-senha-temp-copiado");
  const senhaTempContinuar = document.getElementById("professor-senha-temp-continuar");

  let pendingRedirectId = null;

  function lockFormAfterCreate() {
    form?.querySelectorAll("input, textarea, select, button[type='submit']").forEach((el) => {
      el.disabled = true;
    });
    formActions?.classList.add("is-hidden");
    feedback?.classList.add("is-hidden");
  }

  function showSenhaTemporaria(senha) {
    if (!senhaTempPanel || !senhaTempInput) return;
    senhaTempInput.value = senha;
    senhaTempPanel.classList.remove("is-hidden");
    lockFormAfterCreate();
    senhaTempPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  senhaTempCopiar?.addEventListener("click", async () => {
    if (!senhaTempInput?.value) return;
    try {
      await navigator.clipboard.writeText(senhaTempInput.value);
    } catch (_) {
      senhaTempInput.select();
      document.execCommand("copy");
    }
    senhaTempCopiado?.classList.remove("is-hidden");
    setTimeout(() => senhaTempCopiado?.classList.add("is-hidden"), 2500);
  });

  senhaTempContinuar?.addEventListener("click", () => {
    if (!pendingRedirectId) return;
    window.location.href = `/professores/${pendingRedirectId}#prof-disp-section`;
  });

  window.ClassCulator?.initDisciplinasList(document.getElementById("prof-form-disc-root"));

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitBtn?.disabled) return;

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
      if (!id && result?.senha_temporaria) {
        pendingRedirectId = result.id;
        showSenhaTemporaria(result.senha_temporaria);
        return;
      }
      window.api.feedback(feedback, "Professor salvo com sucesso.", "is-success");
      if (!id && result?.id) {
        setTimeout(() => {
          window.location.href = `/professores/${result.id}#prof-disp-section`;
        }, 600);
      }
    } catch (err) {
      window.api.feedback(feedback, err.message, "is-danger");
    }
  });

  const dispForm = document.getElementById("disponibilidade-form");
  const dispFeedback = document.getElementById("disp-feedback");

  window.ClassCulator?.initDisponibilidadeGrid(dispForm);

  dispForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const profId = dispForm.dataset.profId;
    const items = window.ClassCulator.collectDisponibilidadeState(dispForm);
    try {
      await window.api.json(`/api/v1/professores/${profId}/disponibilidade`, {
        method: "PUT",
        body: JSON.stringify({ items }),
      });
      window.api.feedback(dispFeedback, "Disponibilidade salva com sucesso.", "is-success");
    } catch (err) {
      window.api.feedback(dispFeedback, err.message, "is-danger");
    }
  });

  if (window.location.hash === "#prof-disp-section") {
    document.getElementById("prof-disp-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initProfessorForm);
} else {
  initProfessorForm();
}
