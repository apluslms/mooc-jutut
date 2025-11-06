$(function () {
  $('.ajaxload').each(function() {
    console.log("Creating ajax loader for", this);
    var self = $(this)
    self.html('<div class="text-center row"><div class="loader"></div></div>');
    var loader = self.find('.row');
    $.get(self.data('url'), function(data) {
      console.log(data);
      console.log($(data));
      var content = $(data).filter('#content')
      loader.remove();
      self.replaceWith(content);
    }).fail(function() {
      loader.find('.loader').remove();
      loader.html('<h1><span class="bi bi-alert" aria-hidden="true"></span> Failed to load data</h1>');
      loader.addClass('alert alert-danger')
    });
  });
});
