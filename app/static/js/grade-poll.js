const form = document.getElementById("gerar-form");
const progresso = document.getElementById("progresso");
const progressoMsg = document.getElementById("progresso-msg");
const btn = document.getElementById("btn-gerar");

const POLL_INTERVAL_MS = 2000;

const STATUS_LABEL = {
  pending: "Aguardando início…",
  running: "Calculando combinações…",
  done: "Concluído",
  failed: "Erro",
};

async function pollUntilDone(gradeId) {
  while (true) {
    let data;
    try {
      data = await window.api.json(`/api/v1/grade/status/${gradeId}`);
    } catch (err) {
      progressoMsg.textContent = `Não foi possível consultar o status: ${err.message}`;
      progresso.classList.remove("is-info");
      progresso.classList.add("is-danger");
      return;
    }

    if (data.status === "done") {
      progressoMsg.innerHTML = `Pronto! Redirecionando para a grade…`;
      progresso.classList.remove("is-info");
      progresso.classList.add("is-success");
      setTimeout(() => (window.location.href = `/grade/${gradeId}`), 800);
      return;
    }

    if (data.status === "failed") {
      progressoMsg.textContent = `Não foi possível gerar: ${data.mensagem || "veja os detalhes na grade."}`;
      progresso.classList.remove("is-info");
      progresso.classList.add("is-danger");
      setTimeout(() => (window.location.href = `/grade/${gradeId}`), 1800);
      return;
    }

    const label = STATUS_LABEL[data.status] || data.status;
    progressoMsg.textContent = `${label} (semestre ${data.semestre})`;

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  btn.classList.add("is-loading");
  progresso.classList.remove("is-hidden", "is-success", "is-danger");
  progresso.classList.add("is-info");
  progressoMsg.textContent = "Enviando pedido ao motor de cálculo…";

  const data = new FormData(form);
  const payload = {
    semestre: data.get("semestre"),
    solver: data.get("solver"),
    timeout_s: parseInt(data.get("timeout_s"), 10),
  };
  try {
    const created = await window.api.json("/api/v1/grade/gerar", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    progressoMsg.textContent = `Pedido recebido (versão ${created.versao}). Calculando…`;
    await pollUntilDone(created.id);
  } catch (err) {
    progresso.classList.remove("is-info");
    progresso.classList.add("is-danger");
    progressoMsg.textContent = `Erro: ${err.message}`;
  } finally {
    btn.classList.remove("is-loading");
  }
});
