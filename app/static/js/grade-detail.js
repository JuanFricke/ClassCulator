/* Filtro por turma + auto-refresh enquanto a grade está em execução. */

(function turmaFilter() {
  const select = document.getElementById("turma-filter");
  if (!select) return;
  const blocks = document.querySelectorAll(".turma-block");
  select.addEventListener("change", () => {
    const value = select.value;
    blocks.forEach((block) => {
      const show = value === "__all__" || block.dataset.turmaId === value;
      block.classList.toggle("is-hidden", !show);
    });
  });
})();

(async function autoRefresh() {
  const root = document.getElementById("grade-detail-root");
  const status = root?.dataset.gradeStatus ?? "";
  if (status !== "pending" && status !== "running") return;

  const id = parseInt(root?.dataset.gradeId ?? "", 10);
  if (Number.isNaN(id)) return;

  const progress = document.getElementById("grade-status-progress");
  progress?.removeAttribute("value");

  for (let i = 0; i < 90; i += 1) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const data = await window.api.json(`/api/v1/grade/status/${id}`);
      if (data.status === "done" || data.status === "failed") {
        window.location.reload();
        return;
      }
    } catch (_) {
      return;
    }
  }
})();

(function technicalLogAnchor() {
  const TARGET_ID = "registro-tecnico-geracao";

  function openAndScrollToTechnicalLog() {
    if (window.location.hash !== `#${TARGET_ID}`) return;
    const target = document.getElementById(TARGET_ID);
    if (!target) return;
    if (target.tagName.toLowerCase() === "details") {
      target.open = true;
    }
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest(`a[href="#${TARGET_ID}"]`);
    if (!link) return;
    event.preventDefault();
    history.replaceState(null, "", `#${TARGET_ID}`);
    openAndScrollToTechnicalLog();
  });

  window.addEventListener("hashchange", openAndScrollToTechnicalLog);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", openAndScrollToTechnicalLog, { once: true });
  } else {
    openAndScrollToTechnicalLog();
  }
})();

(function gradeOrientationToggle() {
  const button = document.getElementById("grade-orientation-toggle");
  if (!button) return;

  const tables = Array.from(document.querySelectorAll(".grade-table"));
  if (!tables.length) return;

  const STORAGE_KEY = "grade:view-orientation";
  const ORIGINAL_LAYOUT = new WeakMap();
  tables.forEach((table) => {
    ORIGINAL_LAYOUT.set(table, table.innerHTML);
  });

  const TRANSPOSED_LAYOUT = new WeakMap();
  let orientation = localStorage.getItem(STORAGE_KEY) === "horizontal" ? "horizontal" : "vertical";

  function updateButtonLabel() {
    const isVertical = orientation === "vertical";
    button.textContent = isVertical ? "Dias na horizontal" : "Dias na vertical";
    button.setAttribute("aria-pressed", String(!isVertical));
  }

  function buildHorizontalLayoutFromOriginal(table) {
    if (TRANSPOSED_LAYOUT.has(table)) {
      return TRANSPOSED_LAYOUT.get(table);
    }

    const source = document.createElement("table");
    source.innerHTML = ORIGINAL_LAYOUT.get(table) || "";

    const dayLabels = Array.from(source.querySelectorAll("thead tr th"))
      .slice(1)
      .map((cell) => cell.textContent?.trim() || "");

    const rows = Array.from(source.querySelectorAll("tbody tr"));
    const slotLabels = rows.map((row) => row.querySelector("th")?.textContent?.trim() || "");
    const grid = rows.map((row) => Array.from(row.querySelectorAll("td")));

    const headerRow = document.createElement("tr");
    headerRow.appendChild(document.createElement("th"));
    slotLabels.forEach((slotLabel) => {
      const th = document.createElement("th");
      th.textContent = slotLabel;
      headerRow.appendChild(th);
    });

    const thead = document.createElement("thead");
    thead.appendChild(headerRow);

    const tbody = document.createElement("tbody");
    dayLabels.forEach((dayLabel, dayIndex) => {
      const row = document.createElement("tr");
      const dayHeader = document.createElement("th");
      dayHeader.className = "grade-day";
      dayHeader.setAttribute("scope", "row");
      dayHeader.textContent = dayLabel;
      row.appendChild(dayHeader);

      for (let slotIndex = 0; slotIndex < slotLabels.length; slotIndex += 1) {
        const originalCell = grid[slotIndex]?.[dayIndex];
        row.appendChild(originalCell ? originalCell.cloneNode(true) : document.createElement("td"));
      }

      tbody.appendChild(row);
    });

    const wrapper = document.createElement("div");
    wrapper.appendChild(thead);
    wrapper.appendChild(tbody);
    const markup = wrapper.innerHTML;
    TRANSPOSED_LAYOUT.set(table, markup);
    return markup;
  }

  function applyOrientation() {
    tables.forEach((table) => {
      if (orientation === "horizontal") {
        table.innerHTML = buildHorizontalLayoutFromOriginal(table);
      } else {
        table.innerHTML = ORIGINAL_LAYOUT.get(table) || "";
      }
    });
    updateButtonLabel();
  }

  button.addEventListener("click", () => {
    orientation = orientation === "vertical" ? "horizontal" : "vertical";
    localStorage.setItem(STORAGE_KEY, orientation);
    applyOrientation();
  });

  applyOrientation();
})();
