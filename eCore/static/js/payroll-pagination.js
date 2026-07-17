(function () {
  function initPagination(group) {
    const items = Array.from(group.querySelectorAll('[data-pagination-item]'));
    if (!items.length) return;

    const pageSize = Math.max(parseInt(group.dataset.pageSize || '5', 10), 1);
    const totalPages = Math.max(Math.ceil(items.length / pageSize), 1);
    const prevBtn = group.querySelector('[data-pagination-prev]');
    const nextBtn = group.querySelector('[data-pagination-next]');
    const pageInfo = group.querySelector('[data-pagination-info]');
    const totalInfo = group.querySelector('[data-pagination-total]');
    const jumpToTop = group.dataset.scrollTop !== 'false';
    let currentPage = 1;

    function render() {
      const start = (currentPage - 1) * pageSize;
      const end = start + pageSize;

      items.forEach((item, index) => {
        item.style.display = index >= start && index < end ? '' : 'none';
      });

      if (prevBtn) prevBtn.disabled = currentPage <= 1;
      if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
      if (pageInfo) pageInfo.textContent = `Page ${currentPage} / ${totalPages}`;
      if (totalInfo) totalInfo.textContent = `${items.length} élément(s)`;

      if (jumpToTop) {
        group.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        if (currentPage > 1) {
          currentPage -= 1;
          render();
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        if (currentPage < totalPages) {
          currentPage += 1;
          render();
        }
      });
    }

    if (totalPages <= 1) {
      const controls = group.querySelector('[data-pagination-controls]');
      if (controls) controls.style.display = 'none';
    }

    render();
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-pagination-group]').forEach(initPagination);
  });
})();
