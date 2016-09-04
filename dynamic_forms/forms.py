from collections import OrderedDict
from django import forms
from django.forms.utils import pretty_name
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

from .fields import LabelField
from .utils import freeze


def auto_type_for_enums(default: str):
    def selector(prop: dict):
        if any(w in prop for w in ('enum', 'titleMap')):
            vals = prop.get('enum')
            if vals is None:
                vals = prop.get('titleMap').values()
            if len(vals) < 6:
                if max(len(str(x)) for x in vals) < 6:
                    return 'radios-inline'
                return 'radios'
            return 'select'
        return default
    return selector


class DynamicFormMetaClass(forms.forms.DeclarativeFieldsMetaclass):
    """
    Helper metaclass to make DynamicForm debuging a bit easier
    """
    def __repr__(cls):
        return "<class '%s.%s' with '%s'>" % (cls.__module__, cls.__name__, cls.__generated_from__)


class DynamicForm(forms.forms.BaseForm, metaclass=DynamicFormMetaClass):
    """
    Provides way to build django form objects from plain data structures
    (once loaded from json for example).

    Design of data structure is based on JSON schema standard and
    https://github.com/json-schema-form/angular-schema-form

    This class should support common cases of above specs.

    All supported parameters for a field object:
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
        'string': auto_type_for_enums('text'),
        'integer': auto_type_for_enums('number'),
        'boolean': 'checkbox',
        #'object': 'fieldset',
        'array': 'array',
        'static': 'help',
    }
    TYPE_MAP = {
        # form types
        'fieldset': (None, None), # a fieldset with legend
        'section': (None, None), # just a div
        'text': (forms.CharField, None), # input with type text
        'textarea': (forms.CharField, forms.Textarea), # a textarea
        'number': (forms.IntegerField, None), # input type number
        'password': (forms.CharField, forms.PasswordInput), # input type password
        'checkbox': (forms.BooleanField, None), # a checkbox
        'checkboxes': (forms.MultipleChoiceField, forms.CheckboxSelectMultiple), # list of checkboxes
        'select': (forms.ChoiceField, None), # a select (single value)
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
    COERCE_FIELD_MAP = {
        forms.ChoiceField: forms.TypedChoiceField,
        forms.MultipleChoiceField: forms.TypedMultipleChoiceField,
    }


    @classmethod
    def create_form_class_from(cls, data: "list of field structs"):
        """
        Construct dynamic form based on data.
        Data is list of field structs (see class doc)
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
                type_ = prop.get('type', 'string')

                # handle special type object: flatten it
                if type_ == 'object':
                    childs = prop.get('properties', None)
                    child_fields = get_fields(childs) if childs else {}
                    for k, v in child_fields.items():
                        fields["%s_%s" % (name, k)] = v
                    continue

                # resolve correct type and classes
                field_type = cls.DATA_TO_TYPE_MAP.get(type_, type_)
                if callable(field_type):
                    field_type = field_type(prop)
                field_class, widget_class = cls.TYPE_MAP.get(field_type, (None, None))
                if not widget_class:
                    widget_class = field_class.widget

                # copy direct options
                field_args = {k: prop[l] for l, k in cls.ARG_MAP.items() if l in prop}
                widget_attrs = {k: prop[l] for l, k in cls.WIDGET_ATTR_MAP.items() if l in prop}

                # enums
                enum = prop.get('enum', None)
                title_map = prop.get('titleMap', {})
                if type(title_map) is list:
                    title_map = {v['value']: v['name'] for v in title_map}
                if title_map and not enum:
                    enum = title_map.keys()
                if enum:
                    choices = tuple((k, title_map.get(k, k)) for k in enum)
                    field_args['choices'] = choices

                if 'disabled' in field_args:
                    field_args.setdefault('required', not field_args['disabled'])

                # add type check for integer choices
                if type_ == 'integer' and field_class in cls.COERCE_FIELD_MAP:
                    field_class = cls.COERCE_FIELD_MAP[field_class]
                    field_args['coerce'] = int
                    if not all(isinstance(x[0], int) for x in field_args.get('choices')):
                        raise ValueError("Not all enums are integers for integer type")


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
    def get_form_class_by(cls, data, frozen=None):
        """
        will cache created forms with normalized params as key
        if params are found from cache, then cached form class is returned
        else new form class is created and cached
        """
        if frozen is None:
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

    # Use template rendering interface from django Forms

    as_table = forms.Form.as_table
    as_ul = forms.Form.as_ul
    as_p = forms.Form.as_p

    def __str__(self):
        return self.as_table()

    def _html_output(self, normal_row, error_row, row_ender, help_text_html, errors_on_separate_row):
        output = []
        for key, value in sorted(self.data.items()):
            output.append(normal_row % {
                'errors': '',
                'label': conditional_escape(pretty_name(key)),
                'field': conditional_escape(str(value)),
                'help_text': '',
                'html_class_attr': '',
                'css_classes': '',
                'field_name': '',
            })
        return mark_safe('\n'.join(output))