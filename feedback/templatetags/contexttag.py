from re import sub
from django import template
from django.forms.utils import flatatt
from django.utils.html import format_html

register = template.Library()

def render_context_tag(tag, tooltip="", value="") -> str:
    attrs = {
        'class': 'context-tag label ' + ('colortag-dark' if tag.font_white else 'colortag-light'),
        'style': 'background-color: {};'.format(tag.color)
    }
    if tooltip:
        attrs['data-toggle'] = 'tooltip'
        attrs['data-trigger'] = 'hover'
        attrs['data-placement'] = 'top'
        attrs['title'] = sub('<[^<]+?>', '', tooltip)
    content = tag.content
    if value:
        content = content.replace("{}", value)
    return format_html(
        '<span {attrs}>{content}</span>',
        content=content,
        attrs=flatatt(attrs),
    )

@register.filter
def contexttag(contexttag, tooltip=""):
    return render_context_tag(contexttag, tooltip)
