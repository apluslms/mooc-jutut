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
    panel.find(".status-tag-container .status-tag").remove();
  }

  /* add status tag to response form */
  function add_status_tag(panel, text, color) {
    var html = '<span class="status-tag label label-' + color + ' pull-right">' + text + '</span>';
    panel.find(".status-tag-container").append(html);
  }

  /* update visible and hidden objects in stateful element */
  function on_state_change(e, new_state) {
    var me = $(this);
    var cur_state = me.data('state') || 'default';
    if (new_state != cur_state) {
      var elems = me.find('[data-onstate]');
      elems.filter(function() {
        return this.dataset.onstate.includes(cur_state);
      }).hide();
      elems.filter(function() {
        return this.dataset.onstate.includes(new_state);
      }).show();
      me.data('state', new_state);
    }
  }

  /* Functions to track form changes and to reset them */
  function form_changed() {
    var form = $(this);
    var stateful = form.closest('.response-message').find('.stateful');
    var changed = false;
    form.find('textarea').each(function() {
      changed = this.value != this.defaultValue;
      return !changed;
    });
    stateful.trigger('state_change', [(changed)?'edit':'pre-edit']);
  }
  function on_textarea_change(e) {
    $(this).closest('form').each(form_changed);
  }


  /* Functions to track form edit state and to cancel it */
  function enter_edit_state() {
    const stateful = $(this).closest('.response-message').find('.stateful');
    stateful.trigger('state_change', ['edit']);
  }
  function on_cancel_button(e) {
    const me = $(this);
    $('#' + me.data('textarea-id')).each(function() {
      const ta = $(this);
      const new_state = ta.hasClass('track-change') ? 'pre-edit' : 'default';
      const stateful = ta.closest('.response-message').find('.stateful');
      stateful.trigger('state_change', [new_state]);
      stateful.find('.unpreview-button').click();
      ta.trigger('exit_edit');
      ta.closest('form').each(function() { this.reset(); });
    });
  }

  /* Buttons for toggling preview state */
  let sStart, sEnd;
  function on_preview_button(e) {
    const me = $(this);
    const toolbar = me.closest('.btn-toolbar');
    $('#' + toolbar.data('textarea-id')).each(function() {
      const ta = $(this);
      sStart = this.selectionStart;
      sEnd = this.selectionEnd;
      ta.hide();
      ta.after('<span class="textarea preview">' + ta.val() + '</span>');
    });
    me.hide();
    me.siblings('.unpreview-button').show().focus();
    toolbar.find('.styling-buttons').children().addClass('disabled');
  }
  function on_unpreview_button(e) {
    const me = $(this);
    const toolbar = me.closest('.btn-toolbar');
    $('#' + toolbar.data('textarea-id')).each(function() {
      const ta = $(this);
      ta.next('span.preview').remove();
      ta.show();
      ta.focus().each(function() {
        this.selectionStart = sStart;
        this.selectionEnd = sEnd;
      });
    });
    me.hide();
    me.siblings('.preview-button').show();
    toolbar.find('.styling-buttons').children().removeClass('disabled');
  }

  /* Styling buttons */
  function addTag(input, tagType) {
    const text = input.value.slice(input.selectionStart, input.selectionEnd);
    const startTag = '<' + tagType + ((tagType == 'a') ? ' href=""' : '') + '>';
    const endTag = '</' + tagType + '>';
    input.setRangeText(startTag + text + endTag);
    if (tagType == 'a') {
      // set selection to where link would be inserted
      const start = input.selectionStart + 9;
      input.setSelectionRange(start, start);
    } else {
      // set selection to inside of tag
      const start = input.selectionStart + startTag.length;
      input.setSelectionRange(start, start + text.length);
    }
  }
  function toggleTag(input, tagType) {
    input.focus();
    // Check if there the tags wrap the selection
    const sStart = input.selectionStart;
    const sEnd = input.selectionEnd;
    const startTag = '<' + tagType + ((tagType == 'a') ? ' href=""' : '') + '>';
    const endTag = '</' + tagType + '>';
    const str = input.value;
    const beforeStrI = str.lastIndexOf(startTag, sStart);
    const afterStrI = str.indexOf(endTag, sEnd);
    if (beforeStrI == -1 || afterStrI == -1) { // no tags
      addTag(input, tagType);
      return;
    }
    const beforeBetween = str.slice(beforeStrI + startTag.length, sStart);
    const afterBetween = str.slice(sEnd, afterStrI);
    if (
      beforeBetween.replaceAll(/<.>|<code>/g, '').length > 0 ||
      afterBetween.replaceAll(/<\/.>|<\/code>/g, '').length > 0
    ) { // excess content between tag and selection
      addTag(input, tagType);
      return;
    }
    // remove tag
    input.setRangeText('', afterStrI, afterStrI + endTag.length);
    input.setRangeText('', beforeStrI, beforeStrI + startTag.length);
    input.setSelectionRange(sStart - startTag.length, sEnd - startTag.length);
  }
  function on_style_button(e) {
    const me = $(this);
    const tagType = me.data('tag');
    const toolbar = me.closest('.btn-toolbar');
    $('#' + toolbar.data('textarea-id')).each(function() {
      toggleTag(this, tagType);
    });
  }
  function on_key_down(e) {
    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case 'b':
          // bold
          toggleTag(e.target, 'b');
          break;
        case 'i':
          // italicize
          toggleTag(e.target, 'i');
          break;
        case 'u':
          // underline:
          toggleTag(e.target, 'u');
          break;
        case 'k':
          // insert link
          addTag(e.target, 'a');
          break;
        default:
          return;
      }
      e.preventDefault();
    }
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
    const src = $(this);
    // create new form-group and select it
    const dst = src.after('<div class="buttons-for-radio respond-btn-container">' +
      '<div class="btn-group segmented" role="group">' +
      '<button type="button" class="btn btn-sm btn-success dropdown-toggle"' +
      ' data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">'+
      '<span class="caret"></span><span class="sr-only">Toggle Dropdown</span>' +
      '</button>' +
      '<ul class="dropdown-menu"></ul>' +
      '</div></div>').next();
    const cont = dst.find('.btn-group.segmented');
    const dropdown = dst.find('.dropdown-menu');
    // for every input radio, create new button
    src.find('input[type="radio"]').each(function() {
      const radio_pure = this;
      const radio = $(this);
      const text = radio.parent().text();
      const color = radio.data('color');
      const tooltip = radio.data('tooltip-text');
      if (!radio.prop('disabled')) {
        const button = $('<button class="btn btn-sm btn-' + color + '" ' +
         'data-toggle="tooltip" data-trigger="hover" title="' + tooltip + '">' +
          text + '</button>');
        if (color == 'success') {
          cont.prepend(button);
        } else {
          dropdown.prepend($('<li></li>').append(button));
        }
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

    var elems = $(this).closest('.feedback-response-pair').find('.reacts-to-status');
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
          panel.find('.response-label-container').html('<a href="'+url+'">Link to this responses update page. Open in new tab!</a>');
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
    dom.find('.replace-with-buttons').each(replace_with_buttons);
    !nohover && dom.find('[data-toggle="tooltip"]').tooltip();
    dom.find('.feedback-status-label').each(update_feedback_status_colors);
    if (!global && dom.prev().is('.panel-heading')) {
      update_group_status(dom);
    }

    // Just hook to events
    dom.find('form.ajax-form').submit(ajax_submit);
    dom.find('textarea.track-change').on('change keyup paste', on_textarea_change);
    dom.find('textarea.textarea').on('enter_edit', enter_edit_state);
    dom.find('.cancel-button').on('click', on_cancel_button);
    dom.find('.preview-button').on('click', on_preview_button);
    dom.find('.unpreview-button').on('click', on_unpreview_button);
    dom.find('.styling-buttons').children().on('click', on_style_button);
    dom.find('textarea.textarea, textarea.track-change').on('keydown', on_key_down);
    dom.find('button.colortag').on('click', ajax_set_tag_state);
    dom.find('.stateful').on('state_change', on_state_change);

    // enable showing styling buttons on click when they don't fit
    dom.find('.toggle-styling-buttons').each((i, elem) => {
      const btn = $(elem);
      btn.popover({
        'trigger': 'click',
        'content': () => {
          return btn.closest('.btn-toolbar').find('.styling-buttons').clone(true);
        },
        'template': '<div class="popover style-buttons" role="tooltip"><div class="arrow"></div><div class="popover-content"></div></div>',
      })
      btn.on('show.bs.popover', (e) => {
        btn.tooltip('hide');
        btn.tooltip('disable');
      });
      btn.on('hide.bs.popover', (e) => btn.tooltip('enable'));
    })

    // timeouts
    dom.find('.upload-status').each(function() {
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

  $('#id_source_course').on('change', function() {
    $(".site-messages").remove();
    const courseId = $(this).val();
    $('#tag-import-preview-container').children().each(function() {
      $(this).addClass('hidden');
    })
    $(`#tag-import-preview-${courseId}`).removeClass('hidden');
  });
});


function toggleShowAll(event) {
  // Keypresses other then Enter and Space should not trigger a command
  if (
    event instanceof KeyboardEvent &&
    event.key !== "Enter" &&
    event.key !== " "
  ) return;

  const collapsed = this.classList.toggle("collapsed");
  this.setAttribute(
    'aria-expanded',
    collapsed ? 'false' : 'true'
    );
  let elems = this.parentElement.getElementsByClassName('only-expanded');
  for (let i = 0; i < elems.length; i++) {
    elems[i].classList.toggle('in');
  }
}


window.addEventListener("load", (event) => {
  /* Set up showall buttons */
  const showallDivs = document.getElementsByClassName("toggle-showall");
  for (let i = 0; i < showallDivs.length; i++) {
    const cur = showallDivs[i];
    cur.onclick = toggleShowAll;
    cur.onkeydown = toggleShowAll;
  }
});

async function copyToClipboard(text, elem) {
  const popoverOpts = {
    template: '<div class="popover" role="tooltip"><div class="arrow"></div><div class="popover-content"></div></div>',
    trigger: 'manual',
  };
  try {
    await navigator.clipboard.writeText(text);
    if (elem) {
      btn = $(elem);
      btn.tooltip('hide').popover({
        ...popoverOpts,
        content: elem.dataset.copyNotification || "'" + text + "' was copied to the clipboard",
      }).popover('show');
      setTimeout(() => { btn.popover('hide'); }, 2000);
    }
  } catch (error) {
    console.error(error.message);
    if (elem) {
      btn = $(elem);
      btn.tooltip('hide').popover({
        ...popoverOpts,
        content: "Unable to copy to clipboard: " + text,
      }).popover('show');
      setTimeout(() => { btn.popover('hide'); }, 5000);
    } else {
      console.log("Unable to copy to clipboard: " + text);
    }
  }
}

/* Fetch conversations from url and return them (read-only) within a div. */
async function studentDiscussionPreview(btn) {
  const url = btn.dataset['url'];
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error("Unable to open URL");
    }
    const bodyText = await response.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(bodyText, "text/html");
    const convs = doc.querySelectorAll('.conversation-panel');
    /* insert convs into contentDiv */
    const contentDiv = document.createElement('div');
    contentDiv.className = 'student-conv-popover-content';
    for (const elem of convs) {
      contentDiv.appendChild(elem.cloneNode(true));
    }
    /* Remove extra content from feedback message */
    const buttons = contentDiv.querySelectorAll('.btn');
    for (const elem of buttons) {
      elem.remove();
    }
    const fbMsgTgle = contentDiv.querySelectorAll('.feedback-message .toggle-showall');
    for (const elem of fbMsgTgle) {
      elem.removeAttribute('title');
      elem.removeAttribute('role');
      elem.removeAttribute('tabindex');
    }
    /* clean up response message, inject text into div rather than embedding form */
    const response_msgs = contentDiv.querySelectorAll('.response-message');
    for (const rsp_msg of response_msgs) {
      const text_content = rsp_msg.querySelector('textarea').innerText;
      if (text_content) {
        const textDiv = document.createElement('div');
        textDiv.className = 'display-response';
        textDiv.innerText = text_content;
        rsp_msg.firstElementChild.replaceWith(textDiv); // replace form with text div
      } else { // no text content, so don't display anything
        rsp_msg.remove();
      }
    }
    return contentDiv;
  } catch (error) {
    console.error("Error:", error);
    return btn.dataset['error'];
  }
}


/* Fetch content from button's data-url page and return the first div
 * (should be the page's primary content) */
async function fetchBtnUrlContent(btn, errorClass) {
  const url = btn.dataset['url'];
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error("Unable to open URL");
    }
    const bodyText = await response.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(bodyText, "text/html");
    const contentDiv = doc.querySelector('div');
    return contentDiv;
  } catch (error) {
    console.error("Error:", error);
    return '<div class="' + errorClass + '">' + btn.dataset['error'] + '</div>';
  }
}


$(function() {
  $('[data-toggle="popover"]').popover();

  const opts = {
    html: true,
    placement: 'bottom',
    trigger: 'focus hover',
    viewport: { selector: 'body', padding: 20 },
    // to reduce issue with scrolling at bottom of page on mobile
    container: 'body',
  };

  /* Popovers stay open the first time they are triggered due to manual "show".
   * Function to manually close popover when clicking or focusing elsewhere. */
  const hideOnFocusOutside = (btn) => {
    ['focusin', 'click'].forEach((evtType) => {
      document.addEventListener(evtType, e => {
        if (!btn.contains(e.target)) {
          $(btn).popover('hide');
        };
      },
      {once: true});
    })
  };

  /* Replace default popover with fetched discussions preview */
  $('.student-conv-prev-btn').one('show.bs.popover', function(e) {
    const btn = e.target;
    $(btn).popover('destroy');
    studentDiscussionPreview(btn)
      .then(function(newContent) {
        $(btn).popover({
          ...opts,
          content: newContent,
          placement: (popover, btn) => {
            if ($('.student-conv-prev-btn').last().is(btn)) return 'bottom auto';
            else return 'bottom';
          },
        }).popover('show');
        hideOnFocusOutside(btn);
      });
  });

  /* Replace default popover with points summary */
  $('.display-points-btn').one('show.bs.popover', function(e) {
    const btn = e.target;
    $(btn).popover('destroy');
    fetchBtnUrlContent(btn, 'points-display')
      .then(function(newContent) {
        $(btn).popover({
          ...opts,
          content: newContent,
          viewport: {selector: '.feedback-response-panel', padding: 6 },
        }).popover('show');
        hideOnFocusOutside(btn);
        $('.points-display [data-toggle="tooltip"]').tooltip();
      });
  });

  /* Replace default popover with response to background questionnaire */
  $('.background-btn').one('show.bs.popover', function(e) {
    const btn = e.target;
    $(btn).popover('destroy');
    fetchBtnUrlContent(btn, 'background-display')
      .then(function(newContent) {
        $(btn).popover({
          ...opts,
          content: newContent,
          placement: (popover, btn) => {
            if ($('.background-btn').last().is(btn)) return 'bottom auto';
            else return 'bottom';
          },
        }).popover('show');
        hideOnFocusOutside(btn);
      });
  });
});
