$(function () {
  // Disable empty fields from filter form
  $("#filter-form").submit(function() {
    $(this).find(":input").filter(function() {return !this.value;})
      .addClass("disabled-for-post")
      .attr("disabled", "disabled");
    return true;
  })
  /* on page unload (just after creating form submission) remove disabled stated for bfcache */
  $(window).on('unload', function() {
    $("#filter-form .disabled-for-post").prop("disabled", false);
    // NOTE: should we do reset here? Page rendered after back action would show form that reflects current page content.
  });

  $('.collapse-on-load').collapse();

  $("#id_feedbackfilter_response_grade").replaceCheckboxesWithButtons();
  $('#filter-form select').chosen({disable_search_threshold: 10});
});

/* Check whether the extra filters were collapsed or not previously and set
to same state */
function setExtraFiltersCollapsedStatus() {
  const state = localStorage.getItem('extra-filters-collapsed');
  if (state) {
    if (!(window.bootstrap && window.bootstrap.Collapse)) return;
    const coll_elems = document.getElementsByClassName('filter-collapse');
    for (let i = 0; i < coll_elems.length; i++) {
      const el = coll_elems[i];
      const inst = window.bootstrap.Collapse.getInstance(el) || new window.bootstrap.Collapse(el, { toggle: false });
      inst.show();
    }
    document.getElementById('filter-container').classList.add('expanded');
    const btn = document.getElementById('extra-filters-btn');
    const label = btn.querySelector('.btn-label');
    if (label) label.textContent = btn.dataset['expandedText'];
  }
}

window.addEventListener("load", setExtraFiltersCollapsedStatus);

function toggleExtraOptions(btn) {
  const collEls = Array.from(document.getElementsByClassName('filter-collapse'));
  if (collEls.length === 0) return;
  if (!(window.bootstrap && window.bootstrap.Collapse)) return;

  const filterContainer = document.getElementById('filter-container');
  const willExpand = !filterContainer.classList.contains('expanded');

  for (const el of collEls) {
    const inst = window.bootstrap.Collapse.getInstance(el) || new window.bootstrap.Collapse(el, { toggle: false });
    willExpand ? inst.show() : inst.hide();
  }

  filterContainer.classList.toggle('expanded', willExpand);
  localStorage.setItem('extra-filters-collapsed', willExpand ? 'show' : '');
  const label = btn.querySelector('.btn-label');
  if (label) label.textContent = btn.dataset[willExpand ? 'expandedText' : 'collapsedText'];
}
