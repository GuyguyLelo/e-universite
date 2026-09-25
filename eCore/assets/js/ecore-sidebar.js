/**
 * e-Core — améliorations menu latéral
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var sidebar = document.querySelector(".ecore-sidebar");
    if (!sidebar) return;

    var path = window.location.pathname;

    sidebar.querySelectorAll(".sidebar-submenu a[href]").forEach(function (link) {
      var href = link.getAttribute("href");
      if (!href || href === "#" || href.indexOf("javascript") === 0) return;
      if (path === href || (href.length > 1 && path.indexOf(href) === 0)) {
        link.classList.add("active");
        var submenu = link.closest(".sidebar-submenu");
        if (submenu) {
          submenu.style.display = "block";
          var parentList = submenu.closest(".sidebar-list");
          if (parentList) {
            var title = parentList.querySelector(".sidebar-title");
            if (title) {
              title.classList.add("active");
              var chevron = title.querySelector(".according-menu i");
              if (chevron) {
                chevron.classList.remove("fa-angle-right");
                chevron.classList.add("fa-angle-down");
              }
            }
          }
        }
      }
    });

    sidebar.querySelectorAll(".sidebar-link.link-nav[href]").forEach(function (link) {
      var href = link.getAttribute("href");
      if (href && (path === href || (href.length > 1 && path.indexOf(href) === 0))) {
        link.classList.add("active");
      }
    });
  });
})();
