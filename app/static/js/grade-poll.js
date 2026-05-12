const form = document.getElementById("gerar-form");
const progresso = document.getElementById("progresso");
const progressoMsg = document.getElementById("progresso-msg");
const btn = document.getElementById("btn-gerar");

const POLL_INTERVAL_MS = 2000;

async function pollUntilDone(gradeId) {
  while (true) {
    let data;
    try {
      data = await window.api.json(`/api/v1/grade/status/${gradeId}`);
    } catch (err) {
      progressoMsg.textContent = `Erro ao consultar status: ${err.message}`;
      progresso.classList.remove("is-info");
      progresso.classList.add("is-danger");
      return;
    }

    if (data.status === "done") {
      progressoMsg.innerHTML = `Concluído! Score = <strong>${
        data.score_penalidade ?? "?"
      }</strong>. Redirecionando…`;
      progresso.classList.remove("is-info");
      progresso.classList.add("is-success");
      setTimeout(() => (window.location.href = `/grade/${gradeId}`), 800);
      return;
    }

    if (data.status === "failed") {
      progressoMsg.textContent = `Falha: ${data.mensagem || "ver detalhes da grade."}`;
      progresso.classList.remove("is-info");
      progresso.classList.add("is-danger");
      setTimeout(() => (window.location.href = `/grade/${gradeId}`), 1500);
      return;
    }

    progressoMsg.textContent = `Status: ${data.status} · solver: ${
      data.solver_usado ?? "—"
    } · semestre: ${data.semestre}`;

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  btn.classList.add("is-loading");
  progresso.classList.remove("is-hidden", "is-success", "is-danger");
  progresso.classList.add("is-info");
  progressoMsg.textContent = "Enfileirando tarefa…";

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
    progressoMsg.textContent = `Grade #${created.id} (v${created.versao}) criada. Aguardando solver…`;
    await pollUntilDone(created.id);
  } catch (err) {
    progresso.classList.remove("is-info");
    progresso.classList.add("is-danger");
    progressoMsg.textContent = `Erro: ${err.message}`;
  } finally {
    btn.classList.remove("is-loading");
  }
});
