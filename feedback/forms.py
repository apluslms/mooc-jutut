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
        widget = {
            'response_msg': forms.Textarea(attrs={'placeholder': 'Response'}),
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.disabled = not self.instance.can_be_responded
        if self.disabled:
            for field in self.fields.values():
                field.disabled = True

    def save(self):
        instance = super().save(commit=False)
        update_response_to_aplus(instance)
        instance.save(update_fields=self.fields.keys())
        return instance
