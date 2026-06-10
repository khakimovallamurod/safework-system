(function () {
  function getEls() {
    return {
      sidebar: document.getElementById('app-sidebar'),
      backdrop: document.getElementById('app-sidebar-backdrop'),
    };
  }

  function openSidebar() {
    var els = getEls();
    if (!els.sidebar || !els.backdrop) return;
    els.sidebar.classList.add('open');
    els.backdrop.classList.add('show');
  }

  function closeSidebar() {
    var els = getEls();
    if (!els.sidebar || !els.backdrop) return;
    els.sidebar.classList.remove('open');
    els.backdrop.classList.remove('show');
  }

  function toggleSidebar() {
    var els = getEls();
    if (!els.sidebar) return;
    if (els.sidebar.classList.contains('open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  function SidebarToggleButton() {
    return React.createElement(
      'button',
      {
        type: 'button',
        className: 'btn btn-outline-secondary btn-sm',
        onClick: toggleSidebar,
        title: 'Menyu',
      },
      React.createElement('i', { className: 'bi bi-list fs-6' })
    );
  }

  function mountSidebarToggle() {
    var node = document.getElementById('react-sidebar-toggle');
    if (node && window.React && window.ReactDOM) {
      var root = ReactDOM.createRoot(node);
      root.render(React.createElement(SidebarToggleButton));
    }

    var els = getEls();
    if (els.backdrop) {
      els.backdrop.addEventListener('click', closeSidebar);
    }

    document.querySelectorAll('#app-sidebar .nav-link').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth <= 991) {
          closeSidebar();
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountSidebarToggle);
  } else {
    mountSidebarToggle();
  }
})();
