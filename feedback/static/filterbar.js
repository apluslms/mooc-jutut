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
    let coll_elems = document.getElementsByClassName('filter-collapse');
    for (let i = 0; i < coll_elems.length; i++) {
      coll_elems[i].classList.add('in');
    }
    document.getElementById('filter-container').classList.add('expanded');
    const btn = document.getElementById('extra-filters-btn');
    btn.innerHTML = btn.dataset['expandedText'];
  }
}

window.addEventListener("load", setExtraFiltersCollapsedStatus);

function toggleExtraOptions(btn) {
  let expand = !document.getElementsByClassName('filter-collapse')[0].classList.contains('in');
  const filterContainer = document.getElementById('filter-container');
  filterContainer.classList.toggle('expanded', expand)
  localStorage.setItem('extra-filters-collapsed', expand ? 'in' : '');
  if (expand) {
    btn.innerHTML = btn.dataset['expandedText'];
  } else {
    btn.innerHTML = btn.dataset['collapsedText'];
  }
}
