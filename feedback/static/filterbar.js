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

	$("#id_feedbackfilter_response_grade, #id_feedbackfilter_flags, #id_feedbackfilter_order_by").replaceCheckboxesWithButtons();
	$('.colortag-choice').each(django_colortag_choice);
	$('#filter-form select').chosen({disable_search_threshold: 10});
});
