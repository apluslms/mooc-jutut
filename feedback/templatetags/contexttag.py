from re import sub
from django import template
from django.forms.utils import flatatt
from django.utils.html import format_html

from ..models import ContextTag

register = template.Library()

def render_context_tag(tag: ContextTag, tooltip="") -> str:
    attrs = {
        'class': 'context-tag label ' + ('colortag-dark' if tag.font_white else 'colortag-light'),
        'style': 'background-color: {};'.format(tag.color)
    }
    if tooltip:
        attrs['data-toggle'] = 'tooltip'
        attrs['data-trigger'] = 'hover'
        attrs['data-placement'] = 'top'
        attrs['title'] = sub('<[^<]+?>', '', tooltip)
    return format_html(
        '<span {attrs}>{content}</span>',
        content=tag.content,
        attrs=flatatt(attrs),
    )

@register.filter
def contexttag(contexttag: ContextTag, tooltip=""):
    return render_context_tag(contexttag, tooltip)
