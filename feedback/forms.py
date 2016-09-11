import logging
from hashlib import md5
from django import forms
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.utils.html import mark_safe

from .models import Feedback
from .utils import update_response_to_aplus


logger = logging.getLogger("feedback.forms")


def get_data_changed_check_value(instance):
    check = md5()
    for k in ('response_msg', 'response_grade', 'response_time'):
        check.update(str(getattr(instance, k)).encode('utf-8'))
    return check.hexdigest()


class HadValue:
    def __init__(self, form):
        self.__form = form

    def __getitem__(self, name):
        return self.__form['orig_' + name].value()


class ResponseForm(forms.ModelForm):
    data_changed_check = forms.CharField(widget=forms.HiddenInput())
    orig_responded = forms.BooleanField(widget=forms.HiddenInput(), required=False)
    orig_response_grade_text = forms.CharField(widget=forms.HiddenInput(), required=False)
    orig_valid_response_grade = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    orig_response_time = forms.DateTimeField(widget=forms.HiddenInput(), required=False)
    ORIG_FIELDS = [
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

        kwargs.setdefault("auto_id", "resp_{}_%s".format(instance.id))
        kwargs.setdefault('initial', {}).update(self.original_fields(instance))
        super().__init__(**kwargs)

        self.disabled = not instance.can_be_responded
        if self.disabled:
            for field in self.fields.values():
                field.disabled = True

        self.had = HadValue(self)
        self.has_expired = False

    def original_fields(self, instance, update=False):
        data = {}
        data['data_changed_check'] = get_data_changed_check_value(instance)
        for k in self.ORIG_FIELDS:
            data['orig_' + k] = getattr(instance, k)

        if update:
            self.initial.update(data)
            self.data = self.data.copy()
            self.data.update(data)
        return data

    def clean_data_changed_check(self):
        data_changed_check = self.cleaned_data['data_changed_check']
        if data_changed_check != self.initial['data_changed_check']:
            self.has_expired = True
            url = reverse('feedback:byuser', kwargs={
                'user_id': self.instance.student.id,
                'exercise_id': self.instance.exercise.id,
            })
            link = '<a href="{url}" target="_blank" class="alert-link">{link_text}</a>'.format(url=url, link_text=_("older versions"))
            msg = _("Someone else has updated this form. See {older_versions_link} for editing.").format(older_versions_link=link)
            raise forms.ValidationError(mark_safe(msg))
        return self.cleaned_data['data_changed_check']

    def save(self):
        logger.debug("Saving response data to database and requesing doing update to submission_url")
        instance = super().save(commit=False)
        update_response_to_aplus(instance)
        instance.save(update_fields=self._meta.fields)
        self.original_fields(self.instance, update=True)
        return instance
