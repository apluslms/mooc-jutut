/* Feedback form automation */
$(function() {
	/* update things when something in form has changed */
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
	};

	/* react to edit in textarea */
	var on_textarea_change = function() {
		$(this).closest('form').each(function() { form_changed.call(this); });
	};

	/* when submit-on-click buttons are clicked/radios changed post the form */
	var on_submit_button = function(e) {
		e.preventDefault();
		var form = $(this).closest('form').submit();
	};

	/* hook reset button to also hide itself and update form state */
	var on_reset_button = function() {
		var me = $(this);
		$('#' + me.data('form-id')).each(function() {
			this.reset();
			form_changed.call(this);
		});
	};

	/* clear status tags from response form */
	var clear_status_tags = function(panel) {
		panel.find(".panel-heading .status-tag").remove();
	};

	/* add status tag to response form */
	var add_status_tag = function(panel, text, color) {
		var html = '<span class="status-tag label label-' + color + ' pull-right">' + text + '</span>';
		panel.find(".panel-heading").append(html);
	};

	/* use ajax to post forms */
	var ajax_submit = function(e) {
		var me = $(this);
		var url = this.action;
		var post_data = me.serialize();
		var panel_id = '#' + me.data('panel-id');
		var panel = $(panel_id);
		clear_status_tags(panel);
		add_status_tag(panel, "Sending...", "default");
		$.ajax({
			type: 'POST',
			url: url,
			data: post_data,
			success: function(data, textStatus, xhr) {
				console.log("Post to '" + url + "' with data '" + post_data + "'");
				var new_panel = $(data).find(panel_id);
				if (new_panel.length > 0) {
					// update form
					$(panel_id).replaceWith(new_panel);
					on_form_insert($(panel_id));
					if (xhr.status == 201) {
						// submission was ok
						console.log(" -> was good");
						add_status_tag($(panel_id), "Saved", "success");
					} else {
						console.log(" -> had errors");
						add_status_tag($(panel_id), "Not saved", "warning");
						add_status_tag($(panel_id), "Has errors", "danger");
					}
				} else {
					// Probably login form...
					console.log(
						" -> Got response with status 200 and content" +
						" that doesn't have panel with id '" + panel_id +
						"'. data was '" + data +
						"'");
					clear_status_tags(panel);
					add_status_tag($(panel_id), "Not saved", "warning");
					add_status_tag($(panel_id), "Login required", "danger");
					alert("You are not logged in, do that in another window and resend the form!");
				}
			},
			timeout: 10000,
			error: function(xhr, textStatus, error) {
				clear_status_tags(panel);
				if (textStatus == "timeout") {
					// act on timeout
					add_status_tag(panel_id, "Update timeouted!", "danger");
				} else {
					// axt on other errors: xhr.status
					add_status_tag(panel_id, "Got error " + xhr.status, "danger");
				}
			},
		});
		e.preventDefault();
	};

	/* call for inserted forms */
	var on_form_insert = function(dom=null) {
		if (dom === null) {
			dom = $(document);
		}

		dom.find('form.ajax-form').submit(ajax_submit);
		dom.find('textarea.track-change').on('change keyup paste', on_textarea_change);
		dom.find('.submit-on-click input').on('change click', on_submit_button);
		dom.find('.reset-button[data-form-id]').on('click', on_reset_button);
		var send_button_div = dom.find('input[data-responded=0]').closest('.col-xs-2');
		send_button_div.prev().removeClass('col-xs-10').addClass('col-xs-12');
		send_button_div.remove();
	};

	/* on page load forms got inserted */
	on_form_insert();
});

