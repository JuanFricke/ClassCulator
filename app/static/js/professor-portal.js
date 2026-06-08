/* Portal do professor: disponibilidade e disciplinas. */

function initProfessorPortal() {
  window.ClassCulator?.initDisponibilidadeGrid(document.getElementById("prof-portal-disp-form"));
  window.ClassCulator?.initDisciplinasList(document.getElementById("prof-portal-disc-root"));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initProfessorPortal);
} else {
  initProfessorPortal();
}
