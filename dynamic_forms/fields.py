from functools import lru_cache
from django.forms import Widget, Field
from django.forms.utils import flatatt
from django.forms.boundfield import BoundField


class LabelWidget(Widget):
    """
    Widget for LabelField
    """
    def render(self, name, value, attrs):
        attrs = self.build_attrs(attrs, name=name)
        if 'class' in attrs:
            attrs['class'] = attrs['class'].replace('form-control', '') # fix bootstrap lib
        if hasattr(self, 'initial'):
            value = self.initial
        return '<span %s>%s</span>' % (flatatt(attrs), value or '')


class LabelField(Field):
    """
    Simple field that shows only 'value' text
    Used with dynamic forms to show text between fields
    """
    widget = LabelWidget

    def __init__(self, *args, **kwargs):
        label = kwargs.setdefault('label', '')
        help_ = kwargs.pop('help_text', None)
        if not 'initial' in kwargs:
            kwargs['initial'] = help_ or label
        kwargs['required'] = False
        super().__init__(*args, **kwargs)

    def clean(self, value):
        self.widget.initial = self.initial
        return None


class EnchantedBoundField(BoundField):
    def css_classes(self, extra_classes=None):
        extra_css_classes = getattr(self.field, 'extra_css_classes', None)
        if extra_css_classes:
            if not extra_classes:
                extra_classes = []
            elif hasattr(extra_classes, 'split'):
                extra_classes = extra_classes.split()
            extra_classes.extend(extra_css_classes)
        return super().css_classes(extra_classes=extra_classes)


class BoundLabelField(EnchantedBoundField):
    auto_id = None


def _get_bound_field(self, form, field_name):
    if isinstance(self, LabelField):
        return BoundLabelField(form, self, field_name)
    return EnchantedBoundField(form, self, field_name)


@lru_cache(maxsize=None)
def get_enchanted_field(field_class, extra=None):
    member_dict = {}
    member_dict.update(extra)
    member_dict['get_bound_field'] = _get_bound_field
    return type(field_class.__name__, (field_class,), member_dict)
