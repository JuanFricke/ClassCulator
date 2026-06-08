const form = document.getElementById("gerar-form");
const progresso = document.getElementById("progresso");
const progressoTitulo = document.getElementById("progresso-titulo-text");
const progressoBar = document.getElementById("progresso-bar");
const progressoFrase = document.getElementById("progresso-frase");
const progressoMsg = document.getElementById("progresso-msg");
const btn = document.getElementById("btn-gerar");
const btnChecar = document.getElementById("btn-checar");
const solverInput = document.getElementById("grade-solver");
const timeoutSlider = document.getElementById("grade-timeout-slider");
const timeoutInput = document.getElementById("grade-timeout");

const POLL_INTERVAL_MS = 2000;
const SLIDER_STEPS = 20;
const MIN_MINUTES = 1;
const MAX_MINUTES = 10;
const PHRASE_INTERVAL_MS = 3500;
const PROGRESS_TICK_MS = 250;
const PROGRESS_CAP = 95;
const FUNNY_PHRASES = [
  "Separando professores que adoram segunda de manhã…",
  "Convencendo a sala de artes a ficar quieta…",
  "Negociando com o horário de Educação Física…",
  "Evitando janelas vazias como quem evita reunião…",
  "Trocando de sala antes que o sinal toque…",
  "Contando quantas aulas cabem numa terça-feira…",
  "Perguntando ao diário de classe se está tudo certo…",
  "Agrupando aulas para ninguém ficar com fome no intervalo…",
  "Reorganizando a grade como quem reorganiza a mochila…",
  "Caçando conflitos de professor em dois lugares ao mesmo tempo…",
  "Esperando o projetor ligar (virtualmente)…",
  "Consultando o calendário escolar com carinho…",
  "Distribuindo aulas de matemática com equilíbrio emocional…",
  "Evitando quinta-feira com seis aulas seguidas…",
  "Alinhando turmas, salas e a vontade de café…",
];

let phraseTimer = null;
let progressTimer = null;
let progressStartMs = null;
let progressDurationMs = null;

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

function pickRandomPhrase(exclude) {
  const pool = exclude ? FUNNY_PHRASES.filter((p) => p !== exclude) : FUNNY_PHRASES;
  return pool[Math.floor(Math.random() * pool.length)];
}

function showFrase(text) {
  if (!progressoFrase) return;
  progressoFrase.textContent = text;
  progressoFrase.classList.remove("is-hidden");
}

function hideFrase() {
  progressoFrase?.classList.add("is-hidden");
}

function showStatusMsg(text) {
  if (!progressoMsg) return;
  progressoMsg.textContent = text;
  progressoMsg.classList.remove("is-hidden");
}

function hideStatusMsg() {
  progressoMsg?.classList.add("is-hidden");
}

function stopPhraseRotation() {
  if (phraseTimer) {
    clearInterval(phraseTimer);
    phraseTimer = null;
  }
}

function startPhraseRotation() {
  stopPhraseRotation();
  showFrase(pickRandomPhrase());
  phraseTimer = setInterval(() => {
    showFrase(pickRandomPhrase(progressoFrase?.textContent));
  }, PHRASE_INTERVAL_MS);
}

function stopTimedProgress() {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
  progressStartMs = null;
  progressDurationMs = null;
}

function setProgressIndeterminate(active) {
  if (!progressoBar) return;
  progressoBar.classList.toggle("is-indeterminate", active);
  if (active) {
    progressoBar.removeAttribute("value");
  } else {
    progressoBar.value = 0;
  }
}

function startTimedProgress(durationSeconds) {
  stopTimedProgress();
  if (!progressoBar || !durationSeconds) return;

  setProgressIndeterminate(false);
  progressDurationMs = durationSeconds * 1000;
  progressStartMs = Date.now();
  progressoBar.value = 0;

  progressTimer = setInterval(() => {
    const elapsed = Date.now() - progressStartMs;
    const pct = Math.min(PROGRESS_CAP, (elapsed / progressDurationMs) * 100);
    progressoBar.value = Math.round(pct);
    if (pct >= PROGRESS_CAP) {
      stopTimedProgress();
    }
  }, PROGRESS_TICK_MS);
}

function completeProgress() {
  stopTimedProgress();
  if (!progressoBar) return;
  setProgressIndeterminate(false);
  progressoBar.value = 100;
}

function stopLoadingUi() {
  stopPhraseRotation();
  stopTimedProgress();
}

function setFormBusy(busy) {
  btn?.toggleAttribute("disabled", busy);
  btnChecar?.toggleAttribute("disabled", busy);
  timeoutSlider?.toggleAttribute("disabled", busy);
}

async function pollUntilDone(gradeId, { timed = false, timeoutS = 60 } = {}) {
  hideStatusMsg();
  if (timed) {
    startTimedProgress(timeoutS);
  } else {
    setProgressIndeterminate(true);
  }
  startPhraseRotation();

  while (true) {
    let data;
    try {
      data = await window.api.json(`/api/v1/grade/status/${gradeId}`);
    } catch (err) {
      stopLoadingUi();
      hideFrase();
      showStatusMsg(`Não foi possível consultar o status: ${err.message}`);
      progresso.classList.remove("is-info");
      progresso.classList.add("is-danger");
      setProgressIndeterminate(false);
      setFormBusy(false);
      return;
    }

    if (data.status === "done") {
      stopPhraseRotation();
      completeProgress();
      showFrase("Pronto! Redirecionando para a grade…");
      progresso.classList.remove("is-info");
      progresso.classList.add("is-success");
      setTimeout(() => (window.location.href = `/grade/${gradeId}`), 800);
      return;
    }

    if (data.status === "failed") {
      stopLoadingUi();
      hideFrase();
      showStatusMsg(`Não foi possível gerar: ${data.mensagem || "veja os detalhes na grade."}`);
      progresso.classList.remove("is-info");
      progresso.classList.add("is-danger");
      setProgressIndeterminate(false);
      setTimeout(() => (window.location.href = `/grade/${gradeId}`), 1800);
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitGrade("cpsat");
});

btnChecar?.addEventListener("click", () => submitGrade("classic"));

async function submitGrade(solver) {
  if (!form || !progresso) return;

  if (solverInput) solverInput.value = solver;
  const isCheck = solver === "classic";

  btn?.classList.add("is-loading");
  btnChecar?.classList.add("is-loading");
  setFormBusy(true);

  progresso.classList.remove("is-hidden", "is-success", "is-danger");
  progresso.classList.add("is-info");
  hideStatusMsg();
  if (progressoTitulo) {
    progressoTitulo.textContent = isCheck
      ? "Checando viabilidade…"
      : "Gerando sua grade…";
  }
  showFrase(
    isCheck
      ? "Procurando a primeira combinação que fecha…"
      : "Enfileirando pedido no motor de cálculo…",
  );
  setProgressIndeterminate(isCheck);
  if (!isCheck) {
    progressoBar.value = 0;
  }

  const data = new FormData(form);
  const payload = { solver: data.get("solver") };
  const timeoutS = parseInt(data.get("timeout_s"), 10);
  if (!isCheck) {
    payload.timeout_s = timeoutS;
  }

  try {
    const created = await window.api.json("/api/v1/grade/gerar", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await pollUntilDone(created.id, { timed: !isCheck, timeoutS });
  } catch (err) {
    stopLoadingUi();
    hideFrase();
    progresso.classList.remove("is-info");
    progresso.classList.add("is-danger");
    showStatusMsg(`Erro: ${err.message}`);
    setProgressIndeterminate(false);
  } finally {
    btn?.classList.remove("is-loading");
    btnChecar?.classList.remove("is-loading");
    setFormBusy(false);
  }
}
