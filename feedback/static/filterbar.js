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

	// covert given ul to set of buttons
	var covert_checkboxes_to_buttons = function() {
		var widget = $(this);
		var group = $('<div class="btn-group"></div>');
		widget.after(group);
		widget.find('input:input, input:radio').each(function() {
			var input = $(this);
			var button = $('<button type="button" class="btn"></button>');
			group.append(button);
			var settings = {
				on: {
					icon: 'glyphicon glyphicon-' + (input.data('on-icon') || 'check'),
					text: input.data('on-text') || input.parent().text().trim(),
					color: input.data('on-color') || input.data('color') || 'primary',
				},
				off: {
					icon: 'glyphicon glyphicon-' + (input.data('off-icon') || 'unchecked'),
					text: input.data('off-text') || input.parent().text().trim(),
					color: input.data('off-color') || 'default',
				},
			};

			if (input.is(":radio")) {
				button.on('click', function () {
					input.prop('checked', true);
					input.closest('ul').find('input:radio').each(function() { $(this).triggerHandler('change'); });
				});
			} else {
				button.on('click', function () {
					input.prop('checked', !input.is(':checked'));
					input.triggerHandler('change');
				});
			}
			input.on('change', function () {
				var isChecked = input.is(':checked');
				var opts = settings[isChecked ? "on" : "off"];
				var not = settings[isChecked ? "off" : "on"];
				button.removeClass('btn-' + not.color).addClass('btn-' + opts.color);
				if (isChecked) button.addClass('active');
				else button.removeClass('active');
				button.html('<i class="' + opts.icon + '"></i> ' + opts.text);
			});

			// init style
			input.triggerHandler('change');
		});
		widget.addClass('hidden');
	};
	$("#id_feedbackfilter_response_grade, #id_feedbackfilter_flags, #id_feedbackfilter_order_by").each(covert_checkboxes_to_buttons);
});
