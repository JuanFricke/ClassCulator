/* Gera um link de convite de professor e copia para a área de transferência. */

const gerarBtn = document.getElementById("btn-gerar-convite");
const copiarBtn = document.getElementById("btn-copiar-convite");
const resultado = document.getElementById("convite-resultado");
const urlInput = document.getElementById("convite-url");
const feedback = document.getElementById("convite-feedback");

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_) {
    if (urlInput) {
      urlInput.focus();
      urlInput.select();
      try {
        return document.execCommand("copy");
      } catch (_e) {
        return false;
      }
    }
    return false;
  }
}

gerarBtn?.addEventListener("click", async () => {
  gerarBtn.classList.add("is-loading");
  try {
    const data = await window.api.json("/convites/gerar", {
      method: "POST",
      body: "{}",
    });
    if (urlInput) urlInput.value = data.url;
    resultado?.classList.remove("is-hidden");
    const copied = await copyToClipboard(data.url);
    window.api.feedback(
      feedback,
      copied
        ? "Link copiado! Cole e envie ao professor (uso único)."
        : "Link gerado. Use o botão Copiar ou selecione o texto acima.",
      copied ? "is-success" : "is-warning",
    );
  } catch (err) {
    window.api.feedback(feedback, `Não foi possível gerar o link: ${err.message}`, "is-danger");
  } finally {
    gerarBtn.classList.remove("is-loading");
  }
});

copiarBtn?.addEventListener("click", async () => {
  if (!urlInput || !urlInput.value) return;
  const copied = await copyToClipboard(urlInput.value);
  window.api.feedback(
    feedback,
    copied ? "Link copiado!" : "Não foi possível copiar automaticamente.",
    copied ? "is-success" : "is-warning",
  );
});
