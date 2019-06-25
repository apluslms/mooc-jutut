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

	$("#id_feedbackfilter_response_grade").replaceCheckboxesWithButtons();
	$("#id_feedbackfilter_newest," +
		"#id_feedbackfilter_read," +
		"#id_feedbackfilter_graded," +
		"#id_feedbackfilter_manually," +
		"#id_feedbackfilter_responded," +
		"#id_feedbackfilter_upload").replaceInputsWithMultiStateButtons({
			multi_icon: true,
			icon_on_0: 'fas fa-question-circle',
			icon_off_0: 'far fa-question-circle',
			color_0: 'default',
			icon_on_1: 'fas fa-check-circle',
			icon_off_1: 'far fa-check-circle',
			color_1: 'primary',
			icon_on_2: 'fas fa-dot-circle',
			icon_off_2: 'far fa-dot-circle',
			color_2: 'info',
		});
	$("#id_feedbackfilter_order_by").replaceInputsWithMultiStateButtons({
		icon_0: 'fas fa-sort-amount-down-alt',
		icon_1: 'fas fa-sort-amount-down',
		color_0: 'info',
	})
	$('.colortag-choice').each(django_colortag_choice);
	$('#filter-form select').chosen({disable_search_threshold: 10});
	$('.collapse-on-load').collapse();
});
