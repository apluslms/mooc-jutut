from django import template

register = template.Library()

@register.filter(name="add_bs_class")
def add_bs_class(field, css):
    """
    Safely add CSS classes to a Django form field widget from a template.
    Usage: {{ field|add_bs_class:'form-control' }}
    If the widget already has class(es), append to them.
    """
    w = field.field.widget
    existing = w.attrs.get('class', '')
    # Merge without duplicates while preserving order
    existing_parts = [c for c in existing.split() if c]
    new_parts = [c for c in str(css).split() if c]
    merged = existing_parts[:]
    for c in new_parts:
        if c not in merged:
            merged.append(c)
    return field.as_widget(attrs={'class': ' '.join(merged)})
