$(function() {
  var setlang = function() {
    var val = $(this).data('lang');
    if (val) {
      $('#language-form input[name="language"]').val(val);
      $('#language-form').submit();
    }
  };


  $('#language-select a[data-lang!=""]').on('click', setlang);
  $('#language-menu').show();
});
