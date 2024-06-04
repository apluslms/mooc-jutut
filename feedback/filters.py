import datetime
import re
from typing import Optional, Union

from django.db import models
import django_filters
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from django_colortag.filters import ColortagIEAndOrFilter

from .models import (
    Student,
    StudentTag,
    Exercise,
    Feedback,
    FeedbackQuerySet,
    FeedbackTag,
)


PRIMITIVE_TYPES = (int, float, str)
EMPTY_VALUES = ('', False, slice(None, None, None))

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


def validate_regex(value: str):
    """Check if the value is a valid regex pattern."""
    try:
        re.compile(value)
    except re.error as exc:
        raise ValidationError(
            _("Not a valid regex pattern"),
            code="invalid"
        ) from exc


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

    def compress(self, dates): # pylint: disable=arguments-renamed
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

class SegmentedSelect(forms.RadioSelect):
    template_name = "feedback/widgets/segmented_select.html"
    option_template_name = "feedback/widgets/segmented_option.html"

    def __init__(self, attrs=None, choices=()):
        add_classes = "segmented-select sm"
        if not attrs:
            attrs = {
                "class": add_classes,
            }
        elif not attrs.get("class"):
            attrs["class"] = add_classes
        else:
            attrs["class"] += " " + add_classes
        super().__init__(attrs, choices)

class FlagWidget(forms.MultiWidget):
    template_name = "feedback/widgets/flag_multiwidget.html"

    def __init__(self, attrs=None):
        widgets = tuple(
            SegmentedSelect(attrs, fg.choices) for fg in FeedbackQuerySet.FLAG_GROUPS
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value is None:
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


class ComboTextSearchWidget(forms.MultiWidget):
    """Widget for displaying a text search field with a checkbox
    that allows using another search method.
    The checkbox label and helptext need to be defined through widget
    attributes 'bool_label' and 'bool_helptext'.
    """
    template_name = "feedback/widgets/combo_textsearch_widget.html"

    def __init__(self, attrs=None) -> None:
        widgets = {
            'text': forms.TextInput(attrs=attrs),
            'regex': forms.CheckboxInput(attrs=attrs),
        }
        super().__init__(widgets, attrs)

    def decompress(self, value: Optional[tuple[str, bool]]) -> Union[tuple[str, bool], tuple[None, None]]:
        if value:
            return value
        return (None, None)


class ComboTextSearchField(forms.MultiValueField):
    widget = ComboTextSearchWidget

    def __init__(self, *args, **kwargs) -> None:
        fields = (
            forms.CharField(required=False),
            forms.BooleanField(required=False),
        )
        kwargs.setdefault('require_all_fields', False)
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list: tuple[str, bool]) -> tuple[str, bool]:
        return data_list

    def validate(self, value: tuple[str, bool]) -> None:
        """Validate field value, especially when regex search is used.
        If an another search method is used as alternative instead of
        regex or iregex, this method should be overwritten.
        """
        super().validate(value)
        # if regex search is selected, check that string is valid regex
        if value[1]:
            validate_regex(value[0])


class ComboTextSearchFilter(django_filters.CharFilter):
    """Text search filter that supports two different search methods.
    By default, the filter uses the filter_text method of the queryset.
    However, if the checkbox is selected, uses alternative method for
    searching (which is by default case-insensitive regex search).
    """
    field_class = ComboTextSearchField

    def __init__(self, *args, lookup_expr=None, **kwargs) -> None:
        if lookup_expr is None:
            lookup_expr = 'iregex'
        super().__init__(*args, lookup_expr=lookup_expr, **kwargs)

    def filter(self, qs: FeedbackQuerySet, value: tuple[str, bool]) -> FeedbackQuerySet:
        text_val, cb_val = value
        if text_val:
            if cb_val: # checkbox selected, use alternative search method
                lookup = "%s__%s" % (self.field_name, self.lookup_expr)
                return qs.filter(**{lookup: text_val})
            # use our default method
            return qs.filter_text(self.field_name, text_val)
        return qs


class ContainsTextFilter(django_filters.BooleanFilter):
    field_class = forms.BooleanField

    def filter(self, qs, value):
        if value:
            return qs.filter_contains_text_content()
        return qs


class OrderingFilter(django_filters.filters.ChoiceFilter):
    """Simple ordering filter that works with radio select"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', forms.Select)
        kwargs.setdefault('empty_label', None)
        super().__init__(*args, **kwargs)

    def filter(self, qs, value):
        if is_empty_value(value):
            return qs

        return qs.order_by(value)


class PaginateByFilter(django_filters.filters.Filter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, widget=forms.HiddenInput)

    def filter(self, qs, value):
        # This filter doesn't modify the queryset (no filtering)
        return qs


class FeedbackFilterForm(forms.Form):
    """Add 00:00 times to timestamp inputs"""
    template_name = "manage/filter_form.html"

    def __init__(self, *args, initial=None, **kwargs):
        if not initial:
            initial = {}
        kwargs.setdefault('auto_id', 'id_feedbackfilter_%s')
        super().__init__(*args, initial=initial, **kwargs)

    @property
    def contains_data(self):
        if not hasattr(self, 'cleaned_data'):
            return False
        if self.errors:
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
            ('exercise', _('Exercise order')),
            ('-exercise', _('Reverse exercise order')),
    )
    ORDER_BY_DEFAULT = '-timestamp'

    response_grade = MultipleChoiceFilter(choices=Feedback.GRADE_CHOICES,
                                          extra_filter=lambda q: q.exclude(response_time=None),
                                          widget=forms.CheckboxSelectMultiple())
    flags = FlagFilter(label=_("Flags"))
    tags = ColortagIEAndOrFilter(
        queryset=FeedbackTag.objects.none(),
        field_name='conversation__tags',
        label=_("Feedback tags"),
    )
    student_tags = ColortagIEAndOrFilter(
        queryset=StudentTag.objects.none(),
        field_name='student__tags', label=_("Student tags"),
    )
    exercise = django_filters.ModelChoiceFilter(queryset=Exercise.objects.none())
    student = django_filters.ModelChoiceFilter(queryset=Student.objects.none())
    timestamp = DateTimeFromToRangeFilter(label=_("Timestamp"))
    path_key = django_filters.CharFilter(
        lookup_expr='iregex',
        label=_("Exercise identifier"),
        validators=[validate_regex],
        help_text=_(
            "Filter based on the exercise path key (typically of the "
            "format 'modulekey_chapterkey_exercisekey'). "
            "The filter uses case-insensitive regular expression match."
        )
    )
    student_text = ComboTextSearchFilter(
        field_name='form_data',
        label=_("Student content"),
        help_text=_(
            "Filter conversations based on content of the student "
            "feedback responses. Unfortunately this includes the field "
            "names as well as non-textual responses. "
            "The operators 'AND', 'OR' and 'NOT' (case-sensitive) are supported. "
            "Otherwise the search is case-insensitive."
        ),
    )
    student_text.field.widget.attrs.update({
        'bool_label': _('Use regex search'),
        'bool_helptext': _('Override default search method and use case-insensitive regex search instead.'),
        'class': 'combosearch',
    })
    teacher_text = ComboTextSearchFilter(
        field_name='response_msg',
        label=_("Teacher content"),
        help_text=_(
            "Filter conversations based on text in the teacher responses. "
            "The operators 'AND', 'OR' and 'NOT' (case-sensitive) are supported. "
            "Otherwise the search is case-insensitive."
        ),
    )
    teacher_text.field.widget.attrs.update({
        'bool_label': _('Use regex search'),
        'bool_helptext': _('Override default search method and use case-insensitive regex search instead.'),
        'class': 'combosearch',
    })
    contains_text = ContainsTextFilter(
        label=_("Display only feedback with text content"),
        help_text=_(
            "Filter out automatically graded feedback. Display only "
            "responses that contain text responses as well as feedback "
            "that a teacher has responded to."
        )
    )

    order_by = OrderingFilter(label=_("Sort"),
                              choices=ORDER_BY_CHOICE,
                              initial=ORDER_BY_DEFAULT)
    paginate_by = PaginateByFilter()

    class Meta:
        model = Feedback
        form = FeedbackFilterForm
        fields = (
            'exercise',
            'student',
            'timestamp',
            'path_key',
            'contains_text',
            'student_text',
            'teacher_text',
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
        form.fields['response_by'].queryset = course.staff.exclude(is_staff=True)
        feedbacktags = FeedbackTag.objects.filter(course=course).all()
        form.fields['tags'].set_queryset(feedbacktags)
        studenttags = StudentTag.objects.filter(course=course).all()
        form.fields['student_tags'].set_queryset(studenttags)
        form.fields['paginate_by'].initial = self.data.get('paginate_by', None)
        return form
