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
    return select_from_list(grade, colors) or 'default'


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
