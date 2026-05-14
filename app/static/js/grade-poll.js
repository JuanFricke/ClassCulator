const form = document.getElementById("gerar-form");
const progresso = document.getElementById("progresso");
const progressoMsg = document.getElementById("progresso-msg");
const btn = document.getElementById("btn-gerar");
const timeoutSlider = document.getElementById("grade-timeout-slider");
const timeoutValue = document.getElementById("timeout-value");
const timeoutInput = document.getElementById("grade-timeout");

const POLL_INTERVAL_MS = 2000;
const SLIDER_STEPS = 20;
const MIN_MINUTES = 1;
const MAX_MINUTES = 10;

const STATUS_LABEL = {
  pending: "Aguardando início…",
  running: "Calculando combinações…",
  done: "Concluído",
  failed: "Erro",
};

function sliderMinutes(stepValue) {
  const step = Number(stepValue);
  const ratio = (step - 1) / (SLIDER_STEPS - 1);
  return MIN_MINUTES + ratio * (MAX_MINUTES - MIN_MINUTES);
}

function syncTimeoutFromSlider() {
  const slider = document.getElementById("grade-timeout-slider");
  const valueEl = document.getElementById("timeout-value");
  const hiddenEl = document.getElementById("grade-timeout");
  if (!slider) return;
  const minutes = sliderMinutes(slider.value);
  if (hiddenEl) hiddenEl.value = String(Math.round(minutes * 60));
  if (valueEl) valueEl.textContent = `${minutes.toFixed(1).replace(".", ",")} min`;
  const ratio = (Number(slider.value) - 1) / (SLIDER_STEPS - 1);
  slider.style.setProperty("--cc-slider-fill", `${ratio * 100}%`);
}
window.syncTimeoutFromSlider = syncTimeoutFromSlider;

timeoutSlider?.addEventListener("input", syncTimeoutFromSlider);
timeoutSlider?.addEventListener("change", syncTimeoutFromSlider);
["pointerdown", "mousedown", "touchstart", "click"].forEach((evt) => {
  timeoutSlider?.addEventListener(evt, (e) => e.stopPropagation());
});
syncTimeoutFromSlider();

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
