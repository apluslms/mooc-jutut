from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def updated_query(context, **kwargs):
    query = context['request'].GET.copy()
    for k, v in kwargs.items():
        if v is not None:
            query[k] = v
        else:
            query.pop(k, None)
    return query.urlencode()
