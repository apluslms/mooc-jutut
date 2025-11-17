from typing import Optional

from django import template
from django.forms.utils import flatatt
from django.utils.translation import gettext_lazy as _


register = template.Library()


@register.filter
def select_from_list(index, list_):
    if not isinstance(list_, list):
        list_ = [x.strip() for x in list_.split(',')]
    if index is not None:
        try:
            index = int(index)
            if 0 <= index < len(list_):
                return list_[index]
        except ValueError:
            pass
    return None


@register.filter
def grade_color(grade):
    colors = ['danger', 'warning', 'success']
    return select_from_list(grade, colors) or 'secondary'


@register.filter
def grade_submit_tooltip(grade: Optional[int]) -> str:
    tooltip = [
        _("Give 0 points and send response"),
        _("Give half points and send response"),
        _("Give full points and send response"),
    ]
    return select_from_list(grade, tooltip) or _("Grade and send response")


@register.filter
def fill_format_string(fmt, value):
    parts = tuple(value.split(','))
    return fmt % parts


@register.filter
def force_int(string):
    try:
        return int(string)
    except ValueError:
        return None


@register.filter
def countlines(string, range=''): # pylint: disable=redefined-builtin
    range = range.replace(' ',',').replace(':', ',')
    range = [int(x.strip()) for x in range.split(',', 2)[:2]]
    count = string.count('\n') + 1 if string else 0
    if len(range) == 2:
        return max(min(count, range[1]), range[0])
    if len(range) == 1:
        return max(count, range[0])
    return count


@register.filter
def on_state(cur_state, on_state='default'):
    attrs = {
        'data-onstate': on_state,
    }
    if cur_state not in on_state.split():
        attrs['style'] = "display: none;" # hide

    return flatatt(attrs)


@register.filter
def studenttags_for_course(user, course):
    return user.tags.all().filter(course=course).order_by('name')


@register.filter(name="add_bs_class", is_safe=True)
def add_bs_class(field, css):
    """
    Safely add CSS classes to a Django form field widget from a template.
    Usage: {{ field|add_bs_class:'form-control' }}
    If the widget already has class(es), append to them.
    """
    w = field.field.widget
    existing = w.attrs.get('class', '')
    existing_parts = [c for c in existing.split() if c]
    new_parts = [c for c in str(css).split() if c]
    merged = existing_parts[:]
    for c in new_parts:
        if c not in merged:
            merged.append(c)
    return field.as_widget(attrs={'class': ' '.join(merged)})


@register.filter(name="as_bs_field", is_safe=True)
def as_bs_field(field):
    """Render a form field with appropriate Bootstrap 5 class based on widget type.
    - Text-like inputs and Textarea => form-control
    - Select / SelectMultiple => form-select
    - Date/DateTime/Time inputs => form-control
    - Checkbox/Radio/Files/Hidden and group widgets => unchanged
    """
    from django.forms.widgets import (
        Input,
        Select,
        SelectMultiple,
        Textarea,
        DateInput,
        DateTimeInput,
        TimeInput,
        SelectDateWidget,
        CheckboxInput,
        RadioSelect,
        CheckboxSelectMultiple,
        FileInput,
        HiddenInput,
    )

    w = field.field.widget

    # Group/boolean and hidden widgets: render as-is (no class changes here)
    if isinstance(w, (RadioSelect, CheckboxSelectMultiple, CheckboxInput, HiddenInput)):
        return field.as_widget()

    # Dropdowns
    if isinstance(w, (Select, SelectMultiple)):
        return add_bs_class(field, 'form-select')

    # Composite date widget
    if isinstance(w, SelectDateWidget):
        return add_bs_class(field, 'form-select')

    # File inputs in Bootstrap 5 also use form-control
    if isinstance(w, FileInput):
        return add_bs_class(field, 'form-control')

    # Multiline text
    if isinstance(w, Textarea):
        return add_bs_class(field, 'form-control')

    # Date/Time inputs
    if isinstance(w, (DateInput, DateTimeInput, TimeInput)):
        return add_bs_class(field, 'form-control')

    # Generic input widgets (text, number, email, url, etc.)
    if isinstance(w, Input) or getattr(w, 'input_type', None):
        return add_bs_class(field, 'form-control')

    # Fallback: render as-is
    return field.as_widget()
