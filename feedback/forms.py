import logging
from django import forms

from .models import Feedback
from .utils import update_response_to_aplus


logger = logging.getLogger("feedback.forms")


class ResponseForm(forms.ModelForm):
    HAD_FIELDS = [
        'responded',
        'response_grade_text',
        'valid_response_grade',
        'response_time',
    ]

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

        # save original versions for template
        self.had = {k: getattr(instance, k) for k in self.HAD_FIELDS}

        kwargs.setdefault("auto_id", "resp_{}_%s".format(instance.id))
        super().__init__(**kwargs)

        self.disabled = not instance.can_be_responded
        if self.disabled:
            for field in self.fields.values():
                field.disabled = True


    def save(self):
        logger.debug("Saving response data to database and requesing doing update to submission_url")
        instance = super().save(commit=False)
        update_response_to_aplus(instance)
        instance.save(update_fields=self.fields.keys())
        # update had to current
        self.had = {k: getattr(instance, k) for k in self.HAD_FIELDS}
        return instance
