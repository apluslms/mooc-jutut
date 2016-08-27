from django.forms import Widget, Field
from django.forms.utils import flatatt


class LabelWidget(Widget):
    """
    Widget for LabelField
    """
    def render(self, name, value, attrs):
        attrs = self.build_attrs(attrs, name=name)
        if hasattr(self, 'initial'):
            value = self.initial
        return '<p %s>%s</p>' % (flatatt(attrs), value or '')


class LabelField(Field):
    """
    Simple field that shows only 'value' text
    Used with dynamic forms to show text between fields
    """
    widget = LabelWidget

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', '')
        kwargs['required'] = False
        super().__init__(*args, **kwargs)

    def clean(self, value):
        self.widget.initial = self.initial
        return None

