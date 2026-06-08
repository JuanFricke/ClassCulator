/* Lista filtrável de disciplinas com checkboxes (portal + admin). */

(function professorDisciplinasList() {
  const ENSINO_LABELS = {
    fundamental: "Fund.",
    medio: "Médio",
    ambos: "Ambos",
  };

  function disciplinaNome(item) {
    return item?.querySelector(".has-text-weight-semibold")?.textContent?.trim() || "";
  }

  function initDisciplinasList(root) {
    if (!root) return;

    const searchInput = root.querySelector("[data-disc-search]");
    const countEl = root.querySelector("[data-disc-count]");
    const emptyEl = root.querySelector("[data-disc-empty]");
    const selectedListEl = root.querySelector("[data-disc-selected-list]");
    const selectedEmptyEl = root.querySelector("[data-disc-selected-empty]");
    const items = Array.from(root.querySelectorAll(".prof-disc-item"));
    const filterBtns = root.querySelectorAll("[data-disc-ensino-filters] [data-ensino]");
    let ensinoFilter = "all";

    function updateDiscCount() {
      const selected = root.querySelectorAll('input[name="disciplina_ids"]:checked').length;
      if (countEl) {
        countEl.textContent = `${selected} selecionada${selected === 1 ? "" : "s"}`;
      }
    }

    function renderSelectedList() {
      if (!selectedListEl) return;

      selectedListEl.innerHTML = "";
      const checked = Array.from(root.querySelectorAll('input[name="disciplina_ids"]:checked'));
      checked.sort((a, b) =>
        disciplinaNome(a.closest(".prof-disc-item")).localeCompare(
          disciplinaNome(b.closest(".prof-disc-item")),
          "pt-BR",
        ),
      );

      checked.forEach((input) => {
        const item = input.closest(".prof-disc-item");
        const nome = disciplinaNome(item);
        const ensino = item?.dataset.ensino || "";
        const suffix = ENSINO_LABELS[ensino] ? ` (${ENSINO_LABELS[ensino]})` : "";

        const tag = document.createElement("span");
        tag.className = "tag is-link is-light is-clickable";
        tag.textContent = `${nome}${suffix}`;
        tag.title = "Clique para desmarcar";
        tag.addEventListener("click", () => {
          input.checked = false;
          input.dispatchEvent(new Event("change", { bubbles: true }));
        });
        selectedListEl.appendChild(tag);
      });

      selectedEmptyEl?.classList.toggle("is-hidden", checked.length > 0);
    }

    function onSelectionChange() {
      updateDiscCount();
      renderSelectedList();
    }

    function matchesFilters(item) {
      const query = (searchInput?.value || "").trim().toLowerCase();
      const nome = item.dataset.nome || "";
      const ensino = item.dataset.ensino || "";
      if (query && !nome.includes(query)) return false;
      if (ensinoFilter !== "all" && ensino !== ensinoFilter) return false;
      return true;
    }

    function applyDiscFilters() {
      let visible = 0;
      items.forEach((item) => {
        const show = matchesFilters(item);
        item.classList.toggle("is-hidden", !show);
        if (show) visible += 1;
      });
      emptyEl?.classList.toggle("is-hidden", visible > 0);
    }

    searchInput?.addEventListener("input", applyDiscFilters);

    filterBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        ensinoFilter = btn.dataset.ensino || "all";
        filterBtns.forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        applyDiscFilters();
      });
    });

    root.querySelectorAll('input[name="disciplina_ids"]').forEach((input) => {
      input.addEventListener("change", onSelectionChange);
    });

    onSelectionChange();
    applyDiscFilters();
  }

  window.ClassCulator = window.ClassCulator || {};
  window.ClassCulator.initDisciplinasList = initDisciplinasList;
})();
