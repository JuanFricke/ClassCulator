/* Grade de disponibilidade semanal (portal + admin). */

(function professorDisponibilidade() {
  const DISP_FORM_SELECTORS = "#prof-portal-disp-form, #disponibilidade-form";

  function hiddenInputFor(toggle) {
    return toggle.closest("td")?.querySelector(".disp-ind-input");
  }

  function isAvailable(toggle) {
    const hidden = hiddenInputFor(toggle);
    return hidden ? hidden.disabled : toggle.classList.contains("is-success");
  }

  function updateAriaLabel(toggle, available) {
    const label = toggle.getAttribute("aria-label");
    if (!label) return;
    toggle.setAttribute(
      "aria-label",
      label.replace(/: (disponível|indisponível)$/, `: ${available ? "disponível" : "indisponível"}`),
    );
  }

  function setAvailable(toggle, available) {
    const hidden = hiddenInputFor(toggle);
    toggle.classList.toggle("is-success", available);
    toggle.classList.toggle("is-danger", !available);
    toggle.textContent = available ? "✓" : "✗";
    toggle.setAttribute("aria-pressed", available ? "true" : "false");
    updateAriaLabel(toggle, available);
    const td = toggle.closest("td");
    td?.classList.toggle("is-available", available);
    td?.classList.toggle("is-unavailable", !available);
    if (hidden) {
      hidden.disabled = available;
    }
  }

  function toggleAt(toggle, event) {
    event.preventDefault();
    setAvailable(toggle, !isAvailable(toggle));
  }

  function initDisponibilidadeGrid(form) {
    if (!form || form.dataset.dispGridBound === "1") return;
    form.dataset.dispGridBound = "1";

    const toggles = () => form.querySelectorAll(".disp-toggle[data-dia][data-slot]");

    function setAll(available) {
      toggles().forEach((toggle) => setAvailable(toggle, available));
    }

    function setDay(dia, available) {
      form.querySelectorAll(`.disp-toggle[data-dia="${dia}"]`).forEach((toggle) => {
        setAvailable(toggle, available);
      });
    }

    form.addEventListener("click", (event) => {
      const toggle = event.target.closest(".disp-toggle[data-dia][data-slot]");
      if (toggle && form.contains(toggle)) {
        toggleAt(toggle, event);
        return;
      }

      const cell = event.target.closest("td");
      if (cell && form.contains(cell) && !cell.classList.contains("disp-day-actions")) {
        const cellToggle = cell.querySelector(".disp-toggle[data-dia][data-slot]");
        if (cellToggle) {
          toggleAt(cellToggle, event);
          return;
        }
      }

      const btn = event.target.closest("button");
      if (!btn || btn.type === "submit" || !form.contains(btn)) return;

      const action = btn.getAttribute("data-disp-action");
      if (action === "clear") {
        event.preventDefault();
        setAll(true);
        return;
      }
      if (action === "all") {
        event.preventDefault();
        setAll(false);
        return;
      }

      const dayClear = btn.getAttribute("data-disp-day-clear");
      if (dayClear !== null) {
        event.preventDefault();
        setDay(dayClear, true);
        return;
      }

      const dayAll = btn.getAttribute("data-disp-day-all");
      if (dayAll !== null) {
        event.preventDefault();
        setDay(dayAll, false);
      }
    });
  }

  function collectDisponibilidadeState(form) {
    return Array.from(form.querySelectorAll(".disp-toggle[data-dia][data-slot]")).map((toggle) => ({
      dia: parseInt(toggle.dataset.dia, 10),
      slot: parseInt(toggle.dataset.slot, 10),
      disponivel: isAvailable(toggle),
    }));
  }

  function bootDisponibilidadeGrids() {
    document.querySelectorAll(DISP_FORM_SELECTORS).forEach(initDisponibilidadeGrid);
  }

  window.ClassCulator = window.ClassCulator || {};
  window.ClassCulator.initDisponibilidadeGrid = initDisponibilidadeGrid;
  window.ClassCulator.collectDisponibilidadeState = collectDisponibilidadeState;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootDisponibilidadeGrids);
  } else {
    bootDisponibilidadeGrids();
  }
})();
