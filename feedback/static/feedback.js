/* Feedback form automation */
$(function() {
	var form_changed = function() {
		var form = $(this);
		var sts = $('#' + form.data('state-id'));
		var footer = $('#' + form.data('footer-id'));
		var changed = false;
		form.find('textarea').each(function() {
			changed = this.value != this.defaultValue;
			return !changed;
		});
		if (changed) {
			sts.removeClass(sts.data('orig-style'));
			sts.addClass('label-default');
			sts.text('not saved');
			footer.find('.response-time').hide();
			footer.find('.reset-button').show();
		} else {
			sts.removeClass('label-default');
			sts.addClass(sts.data('orig-style'));
			sts.text(sts.data('orig-text'));
			footer.find('.reset-button').hide();
			footer.find('.response-time').show();
		}
	}
	$('textarea.track-change').on('change keyup paste', function() {
		$(this).closest('form').each(function() { form_changed.call(this); });
	});
	$('.submit-on-click input').on('change click', function(e) {
		e.preventDefault();
		var form = $(this).closest('form').submit();
	});
	$('.reset-button[data-form-id]').on('click', function() {
		var me = $(this);
		$('#' + me.data('form-id')).each(function() {
			this.reset();
			form_changed.call(this);
		});
	}).hide();
	$('input[data-responded=0]').hide();
});

