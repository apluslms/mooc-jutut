function dynamic_forms_textarea() {
	var $ = jQuery;

	// setup
	var base = $(this);
	var span = base, spanbox = base, textbox = base;
	var editable = base.is('textarea');
	if (editable) {
		if (base.data('texttarget')) {
			textbox = $(base.data('texttarget')).first();
		}
		textbox.hide();
		span = $('<span class="textarea"></span>');
		span.text(base.val());
		if (base.data('spantarget')) {
			spanbox = $(base.data('spantarget')).first();
			spanbox.show();
		} else {
			spanbox = $('<div></div>');
			spanbox.insertAfter(textbox);
		}
	} else {
		spanbox = $('<div></div>');
		span.replaceWith(spanbox);
	}
	spanbox.addClass('textarea');
	spanbox.append(span);

	var menu = $('<div class="hovermenu btn-group"></div>');
	spanbox.append(menu);

	var addButton = function(symbol, text, action) {
		var btn = $('<button class="btn btn-primary btn-xs" type="button"><span class="glyphicon glyphicon-'+symbol+'"></span> '+text+'</button>"');
		menu.append(btn);
		btn.on('click', action);
		return btn;
	};

	// edit
	if (editable) {
		var turn_edit_on = function() {
			spanbox.hide();
			textbox.show();
			base.trigger('enter_edit');
			// move focus to end
			textbox.find('textarea').focus().each(function() {
				var len = this.value.length;
				this.selectionStart = len;
				this.selectionEnd = len;
			});
		};
		var turn_edit_off = function() {
			textbox.hide();
			spanbox.show();
		};
		addButton('edit', 'Edit', turn_edit_on);
		span.on('dblclick', turn_edit_on);
		base.on('exit_edit', turn_edit_off);
	}

	// copy
	addButton('copy', 'Copy', function() {
		var temp = $("<textarea></textarea>");
		$("body").append(temp);
		temp.val(span.text()).select();
		var ok;
		try { ok = document.execCommand("copy"); }
		catch(e) { ok = false; }
		temp.remove();

		if (ok) {
			console.log("animate!");
			span.stop(true, true);
			var bg = span.css('backgroundColor');
			span.css('backgroundColor', '#1b9c19')
				.animate({'backgroundColor': bg}, 900, function() {
					span.css('backgroundColor', '');
					console.log('ok');
				});
		} else {
			$(this).removeClass('btn-primary').addClass('btn-danger').prop('disabled', true);
		}
	});

	// mono
	addButton('font', 'Mono', function() {
		$(this).toggleClass('active');
		span.toggleClass('codeblock');
	});
}

function dynamic_forms_textareas() {
	jQuery(this).find('span.textarea, textarea.textarea').each(dynamic_forms_textarea);
}
