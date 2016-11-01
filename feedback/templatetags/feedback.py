from django import template
from django.forms.utils import flatatt


register = template.Library()


@register.filter
def grade_color(grade):
    colors = ['danger', 'warning', 'success']
    if grade is not None:
        try:
            grade = int(grade)
            if 0 <= grade < len(colors):
                return colors[grade]
        except ValueError:
            pass
    return 'default'

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
def countlines(string, range=''):
    range = range.replace(' ',',').replace(':', ',')
    range = [int(x.strip()) for x in range.split(',', 2)[:2]]
    count = string.count('\n') + 1 if string else 0
    if len(range) == 2:
        return max(min(count, range[1]), range[0])
    elif len(range) == 1:
        return max(count, range[0])
    else:
        return count


@register.filter
def on_state(cur_state, on_state='default'):
    attrs = {
        'data-onstate': on_state,
    }
    if not on_state.startswith(cur_state):
        attrs['style'] = "display: none;" # hide

    return flatatt(attrs)
