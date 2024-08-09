import logging
from datetime import datetime
from hashlib import md5
from django import forms
from django.urls import reverse
from django.utils.text import format_lazy
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext_lazy as _
from django.utils.html import mark_safe
from django.utils.http import urlencode
from django_colortag.forms import ColorTagForm

from .models import (
    Feedback,
    FeedbackTag,
    ContextTag,
    Course,
)
from .tasks import async_response_upload


logger = logging.getLogger("feedback.forms")


def get_data_changed_check_value(instance):
    check = md5()
    for k in ('response_time', 'response_by_id', 'response_msg', 'response_grade'):
        check.update(str(getattr(instance, k)).encode('utf-8'))
    return check.hexdigest()


class HiddenDatetimeInput(forms.HiddenInput):
    def format_value(self, value):
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
        return super().format_value(value)

    # < Django 1.11
    def _format_value(self, value):
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
        return super()._format_value(value)


class HiddenDateTimeField(forms.DateTimeField):
    widget = HiddenDatetimeInput
    input_formats = ('%Y-%m-%dT%H:%M:%S.%f%z',)

    def prepare_value(self, value):
        # disable conversion to current timezone
        return value


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
    orig_response_time = HiddenDateTimeField(required=False)
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

    def __init__(self, instance, user=None, **kwargs):
        assert instance is not None, "ResponseForm requires feedback instance"
        self._user = user

        kwargs.setdefault("auto_id", "resp_{}_%s".format(instance.id))
        kwargs.setdefault('initial', {}).update(self.original_fields(instance))
        super().__init__(instance=instance, **kwargs)

        self.disabled = not instance.can_be_responded

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
        """Make sure that feedback is not edited by someone else. Called by self.full_clean()"""
        data_changed_check = self.cleaned_data['data_changed_check']
        if data_changed_check != self.initial['data_changed_check']:
            self.has_expired = True
            url = reverse('feedback:list', kwargs={'course_id': self.instance.exercise.course.id})
            url += '?' + urlencode({'student': self.instance.student.id, 'exercise': self.instance.exercise.id})
            link = '<a href="{url}" target="_blank" class="alert-link">{link_text}</a>'.format(
                url=url,
                link_text=_("older versions")
            )
            msg = format_lazy(
                _("Someone else has updated this form. See {older_versions_link} for editing."),
                older_versions_link=link,
            )
            raise forms.ValidationError(mark_safe(msg))
        return data_changed_check

    def clean_response_msg(self):
        """Return validated and cleaned response_msg. Called by self.full_clean()"""
        return self.cleaned_data['response_msg'].strip()

    def get_notify(self):
        old_msg = self.initial['response_msg'] or ''
        old_msg = "".join(old_msg.split())
        new_msg = self.cleaned_data['response_msg'] or ''
        new_msg = "".join(new_msg.split())
        return Feedback.NOTIFY.NORMAL if old_msg != new_msg else Feedback.NOTIFY.NO
        # FIXME: add support for instance.NOTIFY.IMPORTANT

    def save(self): # pylint: disable=arguments-differ
        user = self._user
        if user is None:
            raise RuntimeError("ResponseForm without user, can't be saved.")
        logger.debug("Saving response data to database and requesing doing update to submission_url")

        # Get the instance and update metadata
        instance = super().save(commit=False)
        instance.response_time = timezone_now()
        instance.response_by = user
        instance.response_notify = self.get_notify()
        instance.response_seen = False

        # prepare for upload
        upload = async_response_upload(instance) if self.has_changed() else None

        # save to db and update form internal state
        fields = self._meta.fields + ('response_time', 'response_by', 'response_notify', 'response_seen')
        instance.save(update_fields=fields)
        self.original_fields(instance, update=True)

        # if there is upload, do it now after instance is saved
        if upload:
            logger.debug("Instance has changes, requesting upload to aplus.")
            upload()
        else:
            logger.debug("No changes to response, so no aplus updated needed.")

        return instance


class FeedbackTagForm(ColorTagForm):
    class Meta(ColorTagForm.Meta):
        model = FeedbackTag
        fields = (
            'name',
            'slug',
            'description',
            'color',
            'pinned',
        )

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        exclude.remove('course')
        return exclude


class ContextTagForm(forms.ModelForm):
    class Meta:
        model = ContextTag
        fields = ['question_key', 'response_value', 'color', 'content']


class ImportTagsForm(forms.Form):
    source_course = forms.ModelChoiceField(queryset=None, label=_("Source course"))

    def __init__(self, target_course: Course, course_options: list[Course], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_course = target_course
        self.fields['source_course'].queryset = course_options

    def copy_tags(self) -> list[str]:
        """Copies tags from source course to target course. Copied tags
        are identical to the source tags except for the course field.
        If a tag with the same slug already exists in the target course,
        it is not copied.
        """
        source_course = self.cleaned_data["source_course"]
        source_tags = source_course.tags.all()
        target_tags = self.target_course.tags.all()
        existing_tags = source_tags.filter(slug__in=target_tags.values_list('slug', flat=True))
        importable_tags = source_tags.difference(existing_tags)
        imported_tag_slugs = list(importable_tags.values_list('slug', flat=True))
        if len(importable_tags) > 0:
            FeedbackTag.objects.bulk_create([
                FeedbackTag(
                    course=self.target_course,
                    name=tag.name,
                    slug=tag.slug,
                    description=tag.description,
                    color=tag.color,
                )
                for tag in importable_tags
            ])
            self.target_course.save()
        return imported_tag_slugs
