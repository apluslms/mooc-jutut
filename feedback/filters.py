import datetime
from itertools import chain

from django.db import models
import django_filters
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from django_colortag.filters import ColortagIncludeExcludeFilter, ColortagIEAndOrFilter

from .models import (
    Student,
    StudentTag,
    Exercise,
    Feedback,
    FeedbackQuerySet,
    FeedbackTag,
)


PRIMITIVE_TYPES = (int, float, str)
EMPTY_VALUES = ('', slice(None, None, None))

def is_empty_value(value):
    if isinstance(value, (tuple, list)): # tags
        return (
            all(not v for v in value) or
            (len(value) == 2 and isinstance(value[0], bool) and all(not v for v in value[1]))
        )
    return (
        not isinstance(value, PRIMITIVE_TYPES) and not value or # complex type is False
        value in EMPTY_VALUES # simple type is False
    )


class SplitDateTimeRangeWidget(forms.MultiWidget):
    """Add support to get widgets as parameter"""
    # NOTE: 'wants to be' a reimplementation of django_filters.widgets.DateRangeWidget
    template_name = 'django_filters/widgets/multiwidget.html'
    # suffixes = ['after', 'before']

    def __init__(self, attrs=None):
        widget = forms.SplitDateTimeWidget(
            date_attrs={'type': 'date'},
            time_attrs={'type': 'time', 'step': '1'},
        )
        super().__init__((widget, widget), attrs)

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]


class SplitDateTimeRangeField(forms.MultiValueField):
    """Use split date/time inputs instead of one datetime input"""
    # NOTE: reimplementation of django_filters.fields.RangeField
    widget = SplitDateTimeRangeWidget

    def __init__(self, *args, **kwargs):
        fields = (
            forms.SplitDateTimeField(required=False),
            forms.SplitDateTimeField(required=False),
        )
        kwargs.setdefault('require_all_fields', False)
        super().__init__(fields, *args, **kwargs)

    def clean(self, value):
        if self.disabled and not isinstance(value, list):
            value = self.widget.decompress(value)
        # value: [[date, time], [date, time]]
        if value:
            after, before = value
            if after and after[0] and is_empty_value(after[1]):
                after = (after[0], datetime.time.min)
            if before and before[0] and is_empty_value(before[1]):
                before = (before[0], datetime.time.max)
            value = (after, before)
        return super().clean((value))

    def compress(self, dates):
        if dates and (dates[0] or dates[1]):
            return slice(*dates)
        return None


class DateTimeFromToRangeFilter(django_filters.filters.RangeFilter):
    """Datetime range input using datetime range field with split date/time inputs"""
    field_class = SplitDateTimeRangeField


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


class FlagWidget(forms.MultiWidget):
    template_name = "feedback/widgets/flag_multiwidget.html"

    def __init__(self, attrs=None):
        widgets = (
            forms.Select(attrs, fg.choices) for fg in FeedbackQuerySet.FLAG_GROUPS
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value == None:
            return [None for w in self.widgets]
        return value


class FlagField(forms.MultiValueField):
    widget = FlagWidget

    def __init__(self, *args, **kwargs):
        fields = tuple(
            forms.ChoiceField(
                required=False,
                choices=fg.choices,
            ) for fg in FeedbackQuerySet.FLAG_GROUPS
        )
        kwargs.setdefault('require_all_fields', False)
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        return data_list


class FlagFilter(django_filters.MultipleChoiceFilter):
    field_class = FlagField

    def filter(self, qs, value):
        value = [v for v in value if v] # ignores empty values
        return qs.filter_flags(*value)


class OrderingFilter(django_filters.filters.ChoiceFilter):
    """Simple ordering filter that works with radio select"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', forms.RadioSelect)
        kwargs.setdefault('empty_label', None)
        super().__init__(*args, **kwargs)

    def filter(self, qs, value):
        if is_empty_value(value):
            return qs

        return qs.order_by(value)


class FeedbackFilterForm(forms.Form):
    """Add 00:00 times to timestamp inputs"""

    def __init__(self, *args, initial=None, **kwargs):
        if not initial:
            initial = {}
        kwargs.setdefault('auto_id', 'id_feedbackfilter_%s')
        super().__init__(*args, initial=initial, **kwargs)

    @property
    def contains_data(self):
        if not hasattr(self, 'cleaned_data'):
            return False
        elif self.errors:
            return None
        return any(not is_empty_value(v) for v in self.cleaned_data.values())

    @property
    def number_of_filters(self):
        if not hasattr(self, 'cleaned_data'):
            return 0
        return sum(1 for k, v in self.cleaned_data.items() if k != 'order_by' and not is_empty_value(v))


class FeedbackFilter(django_filters.FilterSet):
    ORDER_BY_CHOICE = (
            ('timestamp', _('Oldest first')),
            ('-timestamp', _('Newest first')),
    )
    ORDER_BY_DEFAULT = '-timestamp'

    response_grade = MultipleChoiceFilter(choices=Feedback.GRADE_CHOICES,
                                          extra_filter=lambda q: q.exclude(response_time=None),
                                          widget=forms.CheckboxSelectMultiple())
    flags = FlagFilter(label=_("Flags"))
    tags = ColortagIEAndOrFilter(queryset=FeedbackTag.objects.none(), label=_("Tags"))
    student_tags = ColortagIEAndOrFilter(queryset=StudentTag.objects.none(), field_name='student__tags', label=_("Student tags"))
    exercise = django_filters.ModelChoiceFilter(queryset=Exercise.objects.none())
    student = django_filters.ModelChoiceFilter(queryset=Student.objects.none())
    timestamp = DateTimeFromToRangeFilter(label=_("Timestamp"))
    path_key = django_filters.CharFilter(lookup_expr='icontains', label=_("Exercise identifier"))
    form_data = django_filters.CharFilter(method='filter_form_data', label=_("Form content"))

    order_by = OrderingFilter(label=_("Order by"),
                              choices=ORDER_BY_CHOICE,
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
            'student_tags',
        )
        filter_overrides = {
            # hack to make django_filters not to complain about jsonfield
            models.JSONField: { 'filterset_class': django_filters.CharFilter },
        }

    def __init__(self, data, *args, course=None, **kwargs):
        assert course, "FeedbackFilter requires course object"
        self._course = course
        if data:
            data = data.copy() # data was immutable
            data.setdefault('order_by', self.ORDER_BY_DEFAULT)
        else:
            data = None
        super().__init__(data, *args, **kwargs)

    @property
    def form(self):
        if hasattr(self, '_form'):
            return self._form
        form = super().form
        course = self._course
        form.fields['exercise'].queryset = Exercise.objects.filter(course=course).all()
        form.fields['student'].queryset = Student.objects.get_students_on_course(course)
        feedbacktags = FeedbackTag.objects.filter(course=course).all()
        form.fields['tags'].set_queryset(feedbacktags)
        studenttags = StudentTag.objects.filter(course=course).all()
        form.fields['student_tags'].set_queryset(studenttags)
        return form

    @staticmethod
    def filter_form_data(queryset, name, value):
        return queryset.filter_data(value)
