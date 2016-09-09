from django import forms

from .models import Feedback
from .utils import update_response_to_aplus


class ResponseForm(forms.ModelForm):

    class Meta:
        model = Feedback
        fields = (
            'response_msg',
            'response_grade',
        )
        widgets = {
            'response_msg': forms.Textarea(),
            'response_grade': forms.RadioSelect(),
        }

    def __init__(self, **kwargs):
        instance = kwargs.get('instance')
        assert instance is not None, "ResponseForm requires feedback instance"
        kwargs.setdefault("auto_id", "response_{}_%s".format(instance.id))
        super().__init__(**kwargs)

        self.disabled = not instance.can_be_responded
        if self.disabled:
            for field in self.fields.values():
                field.disabled = True

    def save(self):
        instance = super().save(commit=False)
        update_response_to_aplus(instance)
        instance.save(update_fields=self.fields.keys())
        return instance
