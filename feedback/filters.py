import datetime
import django_filters
from django import forms
from django.contrib.postgres import fields as pg_fields
from django.utils.translation import ugettext_lazy as _
from django_colortag.filters import ColortagChoiceFilter

from lib.helpers import Enum

from .models import (
    Student,
    Exercise,
    Feedback,
    FeedbackTag,
)

EMPTY_VALUES = ([], (), {}, '', None, slice(None, None, None))


class DateInput(forms.DateInput):
    """use html5 type for date"""
    input_type = 'date'


class TimeInput(forms.TimeInput):
    """use html5 type for time"""
    input_type = 'time'


class DateTimeInput(forms.DateTimeInput):
    """use html5 type for datetime"""
    input_type = 'datetime-local'


class SplitDateTimeWidget(forms.SplitDateTimeWidget):
    """Use html5 typed input fields"""

    def __init__(self, attrs=None, date_format=None, time_format=None):
        widgets = (
            DateInput(attrs=attrs, format=date_format),
            TimeInput(attrs=attrs, format=time_format),
        )
        # NOTE: skip parent init
        super(forms.SplitDateTimeWidget, self).__init__(widgets, attrs)


class RangeWidget(django_filters.widgets.RangeWidget):
    """Add support to get widgets as parameter"""
    # NOTE: should upstream this

    def __init__(self, widgets=None, attrs=None):
        if widgets is None:
            widgets = (forms.TextInput, forms.TextInput)
        # NOTE: skip parent init
        super(django_filters.widgets.RangeWidget, self).__init__(widgets, attrs)


class SplitDateTimeField(forms.SplitDateTimeField):
    def compress(self, data_list):
        """
        If there is no date, there is no datetime
        If there is no time, presume 00:00
        """
        if data_list:
            if data_list[0] is None:
                return None
            if data_list[1] is None:
                data_list[0] = datetime.time()
        return super().compress(data_list)


class DateTimeRangeField(django_filters.fields.RangeField):
    """Use split date/time inputs instead of one datetime input"""
    def __init__(self, *args, **kwargs):
        field = SplitDateTimeField(widget=SplitDateTimeWidget)
        fields = (field, field)
        kwargs['widget'] = RangeWidget(widgets=tuple(field.widget for field in fields))
        super().__init__(fields, *args, **kwargs)


class DateTimeFromToRangeFilter(django_filters.filters.RangeFilter):
    """Datetime range input using datetime range field with split date/time inputs"""
    field_class = DateTimeRangeField


class MultipleChoiceFilter(django_filters.MultipleChoiceFilter):
    """MultipleChoiceFilter with extra_filter option to apply if filter itself was applied"""
    def __init__(self, *args, extra_filter=None, **kwargs):
        self._extra = extra_filter
        super().__init__(*args, **kwargs)

    def filter(self, qs, value):
        fqs = super().filter(qs, value)
        if fqs is not qs and self._extra:
            fqs = self._extra(fqs)
        return fqs


class OrderingFilter(django_filters.filters.ChoiceFilter):
    """Simple ordering filter that works with radio select"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', forms.RadioSelect)
        super().__init__(*args, **kwargs)

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs

        return qs.order_by(value)


class FeedbackFilterForm(forms.Form):
    """Add 00:00 times to timestamp inputs"""

    def __init__(self, *args, initial=None, **kwargs):
        if not initial:
            initial = {}
        placeholder = type('nulldatetime', (datetime.time,),
            {'date': lambda s: None,'time': lambda s: s})()
        initial['timestamp'] = slice(placeholder, placeholder)
        kwargs.setdefault('auto_id', 'id_feedbackfilter_%s')
        super().__init__(*args, initial=initial, **kwargs)

    @property
    def contains_data(self):
        if not hasattr(self, 'cleaned_data'):
            return False
        elif self.errors:
            return None
        return any(v not in EMPTY_VALUES for v in self.cleaned_data.values())


class FeedbackFilter(django_filters.FilterSet):
    ORDER_BY_CHOICE = (
            ('timestamp', _('Oldest first')),
            ('-timestamp', _('Newest first')),
    )
    ORDER_BY_DEFAULT = '-timestamp'

    flags = django_filters.MultipleChoiceFilter(choices=Feedback.objects.get_queryset().FILTER_FLAGS.choices,
                                                widget=forms.CheckboxSelectMultiple(),
                                                method='filter_flags')
    response_grade = MultipleChoiceFilter(choices=Feedback.GRADE_CHOICES,
                                          extra_filter=lambda q: q.exclude(response_time=None),
                                          widget=forms.CheckboxSelectMultiple())
    tags = ColortagChoiceFilter(queryset=FeedbackTag.objects.none())
    exercise = django_filters.ModelChoiceFilter(queryset=Exercise.objects.none())
    student = django_filters.ModelChoiceFilter(queryset=Student.objects.none())
    timestamp = DateTimeFromToRangeFilter()
    path_key = django_filters.CharFilter(lookup_expr='istartswith')
    form_data = django_filters.CharFilter(method='filter_form_data')

    order_by = OrderingFilter(choices=ORDER_BY_CHOICE,
                              initial=ORDER_BY_DEFAULT)

    class Meta:
        model = Feedback
        form = FeedbackFilterForm
        fields = (
            'exercise',
            'student',
            'timestamp',
            'path_key',
            'form_data',
            'response_by',
            'response_grade',
            'flags',
            'tags',
        )
        filter_overrides = {
            # hack to make django_filters not to complain about jsonfield
            pg_fields.JSONField: { 'filter_class': django_filters.CharFilter },
        }

    def __init__(self, data, *args, course=None, **kwargs):
        assert course, "FeedbackFilter requires course object"
        self._course = course
        if not any(any(bool(x) for x in data.getlist(k)) for k in self._meta.fields):
            data = None
        else:
            data = data.copy()
            data.setdefault('order_by', self.ORDER_BY_DEFAULT)
        super().__init__(data, *args, **kwargs)

    @property
    def form(self):
        if hasattr(self, '_form'):
            return self._form
        form = super().form
        course = self._course
        form.fields['exercise'].queryset = Exercise.objects.filter(course=course).all()
        form.fields['student'].queryset = Student.objects.using_namespace(course.namespace).all()
        form.fields['tags'].queryset = FeedbackTag.objects.filter(course=course).all()
        return form

    @staticmethod
    def filter_flags(queryset, name, values):
        return queryset.filter_flags(*values)

    @staticmethod
    def filter_form_data(queryset, name, value):
        return queryset.filter_data(value)
