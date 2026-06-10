(function () {
  function TableTools(props) {
    var rowCount = React.useMemo(function () {
      var table = document.getElementById(props.tableId);
      if (!table) return 0;
      return table.querySelectorAll('tbody tr').length;
    }, [props.tableId]);

    function clearSearch() {
      var input = document.getElementById(props.searchId);
      if (!input) return;
      input.value = '';
      if (input.form) {
        input.form.submit();
      }
    }

    return React.createElement(
      'div',
      { className: 'mb-3 flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2' },
      React.createElement(
        'small',
        { className: 'text-xs text-slate-500' },
        "Jadvaldagi qatorlar soni: " + rowCount
      ),
      React.createElement(
        'button',
        {
          type: 'button',
          className: 'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100',
          onClick: clearSearch
        },
        'Qidiruvni tozalash'
      )
    );
  }

  function mountTools() {
    var mounts = document.querySelectorAll('[id$="-tools"]');
    mounts.forEach(function (node) {
      var tableId = node.getAttribute('data-table-id');
      var searchId = node.getAttribute('data-search-id');
      if (!tableId || !searchId) return;
      var root = ReactDOM.createRoot(node);
      root.render(React.createElement(TableTools, { tableId: tableId, searchId: searchId }));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountTools);
  } else {
    mountTools();
  }
})();
