/* Feedback form automation */
$(function() {
	/* append error notification */
	function append_error_info(selection, msg, klass=null) {
		selection.each(function() {
			var icon = $('<span class="' + (klass||'') + ' label label-danger"><span class="glyphicon glyphicon-alert"></span></span>');
			icon.tooltip({ title: msg });
			$(this).append(icon);
		});
	}

	/* append done notification */
	function append_done_info(selection, msg, klass=null) {
		selection.each(function() {
			var icon = $('<span class="' + (klass||'') + ' label label-success"><span class="glyphicon glyphicon-ok "></span></span>');
			icon.tooltip({ title: msg });
			$(this).append(icon);
		});
	}

	/* clear status tags from response form */
	function clear_status_tags(panel) {
		panel.find(".panel-footer .status-tag").remove();
	}

	/* add status tag to response form */
	function add_status_tag(panel, text, color) {
		var html = '<span class="status-tag label label-' + color + ' pull-right">' + text + '</span>';
		panel.find(".panel-footer").append(html);
	}

	/* show all fields toggle buttons for feedback form */
	function handle_showall_fields(event, active) {
		var button = $(this);
		var panel = button.closest('.feedback-panel');
		panel.find('.data').toggle(active);
		panel.find('.text th').toggle(active);
	}
	function setup_showall_buttons() {
		var elem = $(this);
		var click;
		if (elem.is('button')) {
			elem.addClass('btn');
			click = elem;
		} else {
			click = elem.closest('div');
		}

		elem.makeToggleButton({
			onicon: elem.data('up'),
			officon: elem.data('down'),
			nocolor: true,
			clickHandler: false,
		});
		elem.on('state_change', handle_showall_fields);

		click.on('click', function() {
			$(this).find('.show-all-fields').each(function() {
				$(this).triggerHandler('toggle_state');
			});
		});
	}

	/* update visible and hidden objects in stateful element */
	function on_state_change(e, new_state) {
		var me = $(this);
		var cur_state = me.data('state') || 'default';
		if (new_state != cur_state) {
			var elems = me.find('[data-onstate]');
			elems.filter(function() {
				return cur_state.startsWith(this.dataset.onstate);
			}).hide();
			elems.filter(function() {
				return new_state.startsWith(this.dataset.onstate);
			}).show();
			me.data('state', new_state);
		}
	}

	/* Functions to track form changes and to reset them */
	function form_changed() {
		var form = $(this);
		var stateful = form.closest('.response-panel').find('.stateful');
		var changed = false;
		form.find('textarea').each(function() {
			changed = this.value != this.defaultValue;
			return !changed;
		});
		stateful.trigger('state_change', [(changed)?'edit-new':'default']);
	}
	function on_textarea_change(e) {
		$(this).closest('form').each(form_changed);
	}
	function on_reset_button(e) {
		var me = $(this);
		$('#' + me.data('form-id')).each(function() {
			this.reset();
			form_changed.call(this);
		});
	}

	/* Functions to track form edit state and to cacel it */
	function enter_edit_state() {
		var stateful = $(this).closest('.response-panel').find('.stateful');
		stateful.trigger('state_change', ['edit-old']);
	}
	function on_cancel_button(e) {
		var me = $(this);
		$('#' + me.data('textarea-id')).each(function() {
			var ta = $(this);
			var stateful = ta.closest('.response-panel').find('.stateful');
			stateful.trigger('state_change', ['default']);
			ta.trigger('exit_edit');
			ta.closest('form').each(function() { this.reset(); });
		});
	}

	/* Buttons that replace radio select */
	function on_submit_button(e) {
		e.preventDefault();
		var button = $(this);
		var radio = $(button.data('radio'));
		radio.prop('checked', true);
		button.closest('.buttons-for-radio').find('.btn.active').removeClass('active');
		button.addClass('active');
		button.closest('form').submit();
	}
	function replace_with_buttons() {
		var src = $(this);
		// create new form-group and select it
		var dst = src.after('<div class="form-group buttons-for-radio"><div class="col-xs-12"><div class="btn-group btn-group-justified" role="group"></div></div></div>').next();
		var cont = dst.find('.btn-group');
		// for every input radio, create new button
		src.find('input[type="radio"]').each(function() {
			var radio_pure = this;
			var radio = $(this);
			var text = radio.parent().text();
			var color = radio.data('color');
			if (radio.prop('disabled')) {
				cont.append('<div class="btn-group" role="group"></div>')
			} else {
				cont.append('<div class="btn-group" rule="group"><button class="btn btn-' +
					color + '">' + text + '</button></div>');
				var button = cont.find('button').last();
				button.data('radio', radio_pure).on('click', on_submit_button);
				if (radio.is(':checked'))
					button.addClass('active');
			}
		});
		// hide original form-group
		src.hide();
	}

	/* update colors that reflect the feedback status */
	function get_bootstrap_classes(classes_str) {
		if (classes_str === undefined) return [];
		var colors = ['default', 'primary', 'danger', 'warning', 'success', 'info'];
		var classes = classes_str.split(/\s+/);
		var matches = [];
		classes.forEach(function(class_) {
			var parts = class_.split('-');
			if (parts.length == 2 && colors.indexOf(parts[1]) >= 0) {
				matches.push(class_);
			}
		});
		return matches;
	}
	function replace_bootstrap_classes(classes, color) {
		return classes.map(function(class_) {
			var type_ = class_.split('-', 1)[0];
			return type_ + '-' + color;
		});
	}
	function update_feedback_status_colors() {
		var color = get_bootstrap_classes(this.className);
		if (color.length != 1) {
			console.log("Invalid element for update_feedback_status_colors: " + this);
			return;
		}
		color = color[0].split('-')[1];

		var elems = $(this).closest('.feedback-response-body').find('.reacts-to-status');
		elems.each(function() {
			var old_classes = get_bootstrap_classes(this.className);
			var new_classes = replace_bootstrap_classes(old_classes, color);
			$(this).removeClass(old_classes.join(' ')).addClass(new_classes.join(' '));
		});
	}
	function update_group_status(panel) {
		var color = panel.data('group-color');
		if (color) {
			panel.parent().each(function () {
				var old_classes = get_bootstrap_classes(this.className);
				var new_classes = replace_bootstrap_classes(old_classes, color);
				$(this).removeClass(old_classes.join(' ')).addClass(new_classes.join(' '));
			});
		}
	}

	/* use ajax to post forms */
	function ajax_submit(e) {
		e.preventDefault();
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
				var panel = $(panel_id);
				var new_panel = $(data).find(panel_id);
				if (new_panel.length > 0) {
					// update form
					panel.replaceWith(new_panel);
					panel = new_panel;
					on_form_insert(panel);
					if (xhr.status == 201) {
						// submission was ok
						console.log(" -> was good");
						add_status_tag(panel, "Saved", "success");
					} else {
						console.log(" -> had errors");
						add_status_tag(panel, "Not saved", "warning");
						add_status_tag(panel, "Has errors", "danger");
					}
				} else {
					// Probably login form...
					console.log(
						" -> Got response with status 200 and content" +
						" that doesn't have panel with id '" + panel_id +
						"'. data was '" + data +
						"'");
					clear_status_tags(panel);
					add_status_tag(panel, "Not saved", "warning");
					add_status_tag(panel, "Unknown error", "danger");
					alert("Unknown error occured. See javascript console!");
				}
			},
			timeout: 10000,
			error: function(xhr, textStatus, error) {
				var panel = $(panel_id);
				clear_status_tags(panel);
				add_status_tag(panel, "Not saved", "warning");
				if (textStatus == "timeout") {
					// act on timeout
					add_status_tag(panel, "Update timeouted!", "danger");
				} else if (xhr.status == 403) {
					// no authentication
					add_status_tag(panel, "Not authenticated!", "danger");
					alert("You are not authenticated. Do that in another tab, then open this reponse in another tab and copy input. Then you can refesh this page.");
					panel.find('.panel-footer').html('<a href="'+url+'">Link to this responses update page. Open in new tab!</a>');
				} else {
					// axt on other errors: xhr.status
					add_status_tag(panel, "Server returned " + xhr.status, "danger");
				}
			},
		});
	}

	/* color tags */
	function ajax_set_tag_state() {
		var me = $(this);
		var container = me.parent();
		var errorname = 'error-' + me.data('tagpk');
		var active = me.hasClass('colortag-active');
		// first, make change
		if (active) me.removeClass('colortag-active');
		else me.addClass('colortag-active');
		// get previous or new defer object
		var defer = container.data('rlock') || $.when();
		// connect to defer chain
		container.data('rlock', defer.then(function() {
			var spinner = $('<span class="updating glyphicon glyphicon-refresh gly-spin"></span>');
			container.find('.uploadok, .'+errorname).remove(); // clear old done and error notifications
			container.append(spinner); // add spinner
			var promise = $.Deferred(); // this promise is fulfilled when ajax request is completed, thus we get serialized updates per response
			$.ajax({
				type: active ? 'DELETE' : 'PUT',
				url: me.data('tagurl'),
				timeout: 10000,
				success: function(data, textStatus, xhr) {
					append_done_info(container, "Update of '" + me.text() + "' ok.", 'uploadok');
				},
				error: function(xhr, textStatus, error) {
					// if there was error, revert change
					if (active) me.addClass('colortag-active');
					else me.removeClass('colortag-active');
					// display and log error
					var name = me.text();
					append_error_info(container, (textStatus == 'timeout') ?
						( "Update of '" + name + "' timeouted." ) :
						( "Update of '" + name + "' failed. Server returned " + xhr.status + ". Check js/server logs." ),
						errorname
					);
					console.log("Tag update failed '" + textStatus + "' return code " + xhr.status + " with data: " + xhr.responseText);
				},
				complete: function() {
					spinner.remove(); // remove spinner
					promise.resolve(); // always resolve promise, no failures
				},
			});
			return promise;
		}));
	}

	/* response status */
	function update_response_status(span, nohover) {
		var self = $(span);
		var url = self.data('updateurl');
		var modified = self.data('last_modified');
		//alert("" + url + modified);
		$.ajax({
			type: 'GET',
			url: url,
			timeout: 5000,
			headers: {
				'If-Modified-Since': modified,
			},
			success: function(data, textStatus, xhr) {
				var elem = self;
				if (data) {
					elem = $(data);
					self.replaceWith(elem);
					// new data, do reactions
					!nohover && elem.filter('[data-toggle="tooltip"]').tooltip();
					// remember updateurl
					if (!elem.data('updateurl'))
						elem.data('updateurl', url);
					// record last modified
					elem.data('last_modified', xhr.getResponseHeader("Last-Modified"));
				}
				var code = elem.data('code');
				if (code != '200')
					elem.each(function() {
						var this_ = this;
						setTimeout(update_response_status, 2000, this_, nohover);
					});
			},
			error: function(xhr, textStatus, error) {
				console.log("Status update failed '" + textStatus + "' return code " + xhr.status + " with data: " + xhr.responseText);
				setTimeout(update_response_status, 2000, span, nohover);
			},
		});
	}


	/* test for broken apple mobile devices */
	function is_apple_mobile() {
		var ua = navigator.userAgent;
		var re = /(iPad|iPod|iPhone);/i;
		return re.test(ua);
	}

	/* call for inserted forms */
	function on_form_insert(dom=null) {
		var nohover = is_apple_mobile();
		var global = dom === null;
		if (global) {
			dom = $(document);
			if (nohover)
				dom.find('body').removeClass('ok').addClass('ios');;
		}

		// Modify
		dom.each(dynamic_forms_textareas);
		!nohover && dom.find('[data-toggle="tooltip"]').tooltip();
		dom.find('.replace-with-buttons').each(replace_with_buttons);
		dom.find('.feedback-status-label').each(update_feedback_status_colors);
		dom.find('.show-all-fields').each(setup_showall_buttons);
		dom.find('.show-all-fields').each(function() { $(this).triggerHandler('toggle_state'); });
		if (!global && dom.prev().is('.panel-heading')) {
			update_group_status(dom);
		}

		// Just hook to events
		dom.find('form.ajax-form').submit(ajax_submit);
		dom.find('textarea.track-change').on('change keyup paste', on_textarea_change);
		dom.find('textarea.textarea').on('enter_edit', enter_edit_state);
		dom.find('.reset-button[data-form-id]').on('click', on_reset_button);
		dom.find('.cancel-button').on('click', on_cancel_button);
		dom.find('.colortag').on('click', ajax_set_tag_state);
		dom.find('.stateful').on('state_change', on_state_change);

		// timeouts
		dom.find('.upload_status').each(function() {
			var span = this;
			setTimeout(update_response_status, 2000, span, nohover);
		});
	}

	/* on page load forms got inserted */
	on_form_insert();

	/* setup jquery ajax with csrf token */
	$.ajaxSetup({
		beforeSend: function(xhr, settings) {
			var csrftoken = Cookies.get('csrftoken');
			if (!this.crossDomain && csrftoken) {
				xhr.setRequestHeader("X-CSRFToken", csrftoken);
			}
		}
	});
});

