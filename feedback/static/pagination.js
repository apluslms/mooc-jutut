$(function() {
  $('select.paginate_by').on('change', function(event) {
    /* Change the paginate_by query parameter in the window location to the new selected value. */
    event.preventDefault();
    const params = new URLSearchParams(window.location.search);
    params.set('paginate_by', $(this).val());
    params.delete('page');
    const moddedUrl = new URL(window.location.href);
    moddedUrl.search = params.toString();
    window.location = moddedUrl;
  });
});