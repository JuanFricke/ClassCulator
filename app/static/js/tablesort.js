// Minimal client-side table sorter for tables with class `is-sortable`.
(function () {
  function getCellValue(row, idx) {
    return row.children[idx].dataset.sortValue ?? row.children[idx].innerText.trim();
  }

  function comparer(idx, asc) {
    return function (a, b) {
      const v1 = getCellValue(asc ? a : b, idx);
      const v2 = getCellValue(asc ? b : a, idx);
      const n1 = parseFloat(v1.replace(/[^0-9.,-]/g, '').replace(',', '.'));
      const n2 = parseFloat(v2.replace(/[^0-9.,-]/g, '').replace(',', '.'));
      if (!isNaN(n1) && !isNaN(n2)) return n1 - n2;
      return v1.toString().localeCompare(v2.toString(), undefined, { numeric: true, sensitivity: 'base' });
    };
  }

  function makeSortable(table) {
    const thead = table.tHead;
    if (!thead) return;
    Array.from(thead.querySelectorAll('th')).forEach((th, idx) => {
      if (th.dataset.sort === 'disabled') return;
      th.style.cursor = 'pointer';
      th.addEventListener('click', () => {
        const tbody = table.tBodies[0];
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const asc = !th.classList.contains('sort-asc');
        // clear classes
        thead.querySelectorAll('th').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
        th.classList.add(asc ? 'sort-asc' : 'sort-desc');
        rows.sort(comparer(idx, asc));
        rows.forEach(r => tbody.appendChild(r));
      });
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('table.is-sortable').forEach(makeSortable);
  });
})();
