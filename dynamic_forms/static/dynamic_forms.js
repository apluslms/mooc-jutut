function dynamic_forms_textarea() {
	var $ = jQuery;
	var container = $('<div class="textarea"></div>');
	var span = $(this);
	span.replaceWith(container);
	container.append(span);
	var menu = $('<div class="hovermenu btn-group"></div>');
	container.append(menu);

	var addButton = function(symbol, text, action) {
		var btn = $('<button class="btn btn-primary btn-xs" type="button"><span class="glyphicon glyphicon-'+symbol+'"></span> '+text+'</button>"');
		menu.append(btn);
		btn.on('click', action);
		return btn;
	};

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

	// textarea
	addButton('font', 'Mono', function() {
		$(this).toggleClass('active');
		span.toggleClass('codeblock');
	});
}

function dynamic_forms_textareas() {
	jQuery(this).find('span.textarea').each(dynamic_forms_textarea);
}

jQuery(function($) {
	$('span.textarea').each(dynamic_forms_textarea);
});
