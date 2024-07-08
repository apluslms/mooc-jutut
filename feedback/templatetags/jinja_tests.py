from django_jinja import library
from jinja2 import pass_context

from dynamic_forms.fields import EnchantedBoundField


@library.test(name="has_textfields")
def is_has_textfields(form) -> bool:
    """Check if form has any text fields."""
    for field in form:
        if isinstance(field, EnchantedBoundField) and field.is_text:
            return True
    return False

@library.test(name="primary_textfeedback")
@pass_context
def is_primary_textfeedback(ctx, field) -> bool:
    """Check if this field is the primary text feedback of the form.
    If a form has a question with the flag 'main-feedback', that field
    is the primary text feedback field. If not, the last text feedback
    is considered the primary text feedback.
    """
    if 'main-feedback-question' in field.css_classes():
        return True
    form = ctx.get('form')
    last_text_field = None
    for f in form:
        if isinstance(f, EnchantedBoundField) and f.is_text:
            if 'main-feedback-question' in f.css_classes():
                return False
            last_text_field = f
    return field == last_text_field
