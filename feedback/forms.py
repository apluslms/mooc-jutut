from collections import OrderedDict
from copy import copy

from django import forms
from django.forms.utils import flatatt

from lib.helpers import freeze


class LabelWidget(forms.Widget):
    def render(self, name, value, attrs):
        attrs = self.build_attrs(attrs, name=name)
        if hasattr(self, 'initial'):
            value = self.initial
        return '<p %s>%s</p>' % (flatatt(attrs), value or '')


class LabelField(forms.Field):
    widget = LabelWidget

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', '')
        kwargs['required'] = False
        super().__init__(*args, **kwargs)

    def clean(self, value):
        self.widget.initial = self.initial
        return None


class DummyForm:
    """
    Duck type of django Forms class
    Will wrap full POST data to cleaned_data with some exceptions (csrf for example)
    """
    def __init__(self, data=None, **kwargs):
        self.data = data

    def is_valid(self):
        return True

    @property
    def cleaned_data(self):
        return {(k, v) for k, v in self.data.items() if k not in ['csrfmiddlewaretoken']}

    def __str__(self):
        return str('<!-- No printable form -->')


class DynamicFormMetaClass(forms.forms.DeclarativeFieldsMetaclass):
    """
    Helper metaclass to make DynamicForm debuging a bit easier
    """
    def __repr__(cls):
        return "<class '%s.%s' with '%s'>" % (cls.__module__, cls.__name__, cls.__generated_from__)


class DynamicForm(forms.forms.BaseForm, metaclass=DynamicFormMetaClass):
    """
    Class to set correct metaclass and to provide factory classmethods.

    all supported parameters for a field:
    {
      'key': 'field unique identifier', # name and id is also mapped to this
      'type': valid_type,
      'title': 'title of the field',
      'required': True,
      'disabled': False,
      'placeholder': 'placeholder message',
      'description': 'help/description message',
      'error_message': 'error text shown when field content is not accepted',

      'enum': ['a'. 'b', 'c'], # list of choices for multi and single selects, if missing, keys from titleMap is used
      'titleMap': {
       'a': 'A',
       'b': 'B',
       'c': 'C',
      },
    }
    """

    FORM_CACHE = {}
    DATA_TO_TYPE_MAP = {
        'string': 'text',
        'integer': 'number',
        'boolean': 'checkbox',
        #'object': 'fieldset',
        'array': 'array',
        'static': 'help',
    }
    TYPE_MAP = {
        #'': fp(forms.MultipleChoiceField, widget=forms.CheckboxSelectMultiple),
        #'one': fp(forms.ChoiceField, widget=forms.RadioSelect),
        #'email': forms.EmailField,
        #'bool': forms.BooleanField,
        #'int': forms.IntegerField,
        # form types
        'fieldset': (None, None), # a fieldset with legend
        'section': (None, None), # just a div
        'text': (forms.CharField, None), # input with type text
        'textarea': (forms.CharField, forms.Textarea), # a textarea
        'number': (forms.IntegerField, None), # input type number
        'password': (forms.CharField, forms.PasswordInput), # input type password
        'checkbox': (forms.BooleanField, None), # a checkbox
        'checkboxes': (forms.MultipleChoiceField, forms.CheckboxSelectMultiple), # list of checkboxes
        'select': (forms.ChoiceField, forms.RadioSelect), # a select (single value)
        'radios': (forms.ChoiceField, forms.RadioSelect), # radio buttons
        'radios-inline': (forms.ChoiceField, forms.RadioSelect), # radio buttons in one line
        'radiobuttons': (forms.ChoiceField, forms.RadioSelect), # radio buttons with bootstrap buttons
        'help': (LabelField, None), # insert arbitrary html
        'template': (None, None), # insert an angular template
        'tab': (None, None), # tabs with content
        'array': (None, None), # a list you can add, remove and reorder
        'tabarray': (None, None), # a tabbed version of array
        'actions': (None, None), # horizontal button list, can only submit and buttons as items
        'submit': (None, None), # a submit button
        'button': (None, None), # a button
    }
    ARG_MAP = {
        # input key: django field key
        'title': 'label',
        'required': 'required',
        'disabled': 'disabled',
        'value': 'initial',
        'helpvalue': 'initial', # value when type is help
        'description': 'help_text',
        'validationMessage': 'error_message',
        'error_message': 'error_message',
    }
    WIDGET_ATTR_MAP = {
        # input key: django widget key
        'placeholder': 'placeholder',
    }


    @classmethod
    def create_form_class_from(cls, data):
        """
        Construct dynamic form based on serialized string that is submittable
        trough http query parameters
        """
        def get_fields(properties):
            """Returns list of django form fields for iterable of properties"""
            if isinstance(properties, dict):
                properties = properties.items()

            fields = OrderedDict()
            for i, row in enumerate(properties):
                # get name and prop
                if isinstance(row, dict):
                    # row is object
                    try:
                        name = next((row[k] for k in ['key', 'id', 'name'] if k in row))
                    except StopIteration:
                        name = 'field_%d' % (i,)
                    prop = row
                else:
                    # row is pair (e.g. dict.items())
                    name, prop = row

                # get type
                try:
                    type_ = prop.get('type', 'string')
                except:
                    print("WTFFFF!!!!... ", i, row, prop)
                    raise

                # traverse objects
                if type_ == 'object':
                    childs = prop.get('properties', None)
                    child_fields = get_fields(childs) if childs else {}
                    for k, v in child_fields.items():
                        fields["%s.%s" % (name, k)] = v
                    continue

                # get classes
                type_ = cls.DATA_TO_TYPE_MAP.get(type_, type_)
                field_class, widget_class = cls.TYPE_MAP.get(type_, None)
                if not widget_class:
                    widget_class = field_class.widget

                # copy direct options
                field_args = {k: prop[l] for l, k in cls.ARG_MAP.items() if l in prop}
                widget_attrs = {k: prop[l] for l, k in cls.WIDGET_ATTR_MAP.items() if l in prop}

                # enums
                if 'titleMap' in prop:
                    choices = prop['titleMap']
                    if type(choices) is list:
                        choices = {v['value']: v['name'] for v in choices}
                    if 'enum' in prop:
                        choices = {k: choices.get(k, k) for k in prop['enum']}
                    field_args['choices'] = choices

                if 'disabled' in field_args:
                    field_args.setdefault('required', not field_args['disabled'])


                # initialize classes and add fields
                widget = widget_class(attrs=widget_attrs)
                field = field_class(widget=widget, **field_args)
                fields[name] = field
            return fields

        fields = get_fields(data)
        fields['__generated_from__'] = data
        fields['__module__'] = __name__
        return type(cls.__name__, (cls,), fields)


    @classmethod
    def get_form_class_by(cls, data):
        """
        will cache created forms with normalized params as key
        if params are found from cache, then cached form class is returned
        else new form class is created and cached
        """
        frozen = freeze(data)
        if frozen in cls.FORM_CACHE:
            return cls.FORM_CACHE[frozen]
        form = cls.create_form_class_from(data)
        cls.FORM_CACHE[frozen] = form
        return form


    def clean(self):
        cleaned_data = super().clean()
        # drop fields with none value (LabelField for example)
        return dict((k, v) for k, v in cleaned_data.items() if v is not None)
