from collections import OrderedDict
from django.forms import CharField

from dynamic_forms.forms import DynamicForm
from jutut.appsettings import app_settings

class DynamicFeedbacForm(DynamicForm):
    @classmethod
    def create_form_class_from(cls, data: "list of field structs", i18n):
        form_class = super().create_form_class_from(data, i18n)
        fields = form_class.base_fields # NOTE: changed to .declared_fields in future django releases
        all_text_fields = OrderedDict()
        required_text_fields = OrderedDict()
        optional_text_fields = OrderedDict()

        for name, field in fields.items():
            if isinstance(field, CharField):
                if field.required:
                    required_text_fields[name] = field
                else:
                    optional_text_fields[name] = field
                all_text_fields[name] = field

        form_class.all_text_fields = all_text_fields
        form_class.required_text_fields = required_text_fields
        form_class.optional_text_fields = optional_text_fields
        form_class.is_graded = bool(required_text_fields)

        return form_class

    @property
    def has_optional_answers(self):
        data = self.cleaned_data if hasattr(self, 'cleaned_data') else self.data
        assert bool(data), "Empty form data"

        min_len = app_settings.TEXT_FIELD_MIN_LENGTH
        fields = self.optional_text_fields
        ok = lambda x: bool(x) and len(x) > min_len
        return any(
            ok(data[name]) for name in fields.keys()
        )

    @property
    def requires_manual_check(self):
        return self.is_graded or self.has_optional_answers
