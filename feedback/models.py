import datetime
from collections import namedtuple
from django.db import models, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.postgres import fields as pg_fields
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import get_language, ugettext_lazy as _

from lib.helpers import Enum
from aplus_client.django.models import (
    ApiNamespace as Site, # mooc-jutut refers api namespaces as sites
    NamespacedApiObject,
    NestedApiObject,
)
from dynamic_forms.models import Form


class Student(NamespacedApiObject):
    username = models.CharField(max_length=128)
    full_name = models.CharField(max_length=128)

    def __str__(self):
        return "{s.full_name:s} ({s.username:s})".format(s=self)


class Course(NamespacedApiObject):
    code = models.CharField(max_length=128)
    name = models.CharField(max_length=128)
    html_url = models.CharField(max_length=255)
    language = models.CharField(max_length=5)

    def __str__(self):
        return "{} - {}".format(self.code, self.name)


class ExerciseManager(NestedApiObject.Manager):
    def with_course(self):
        return self.get_queryset().select_related('course')


class Exercise(NestedApiObject):
    NAMESPACE_FILTER = 'course__namespace'

    objects = ExerciseManager()

    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    html_url = models.CharField(max_length=255)
    course = models.ForeignKey(Course,
                               related_name='exercises',
                               on_delete=models.PROTECT)

    @property
    def namespace(self):
        return self.course.namespace

    def get_forms(self, path_key=None):
        filters = dict(feedbacks__exercise=self)
        if path_key:
            filters['feedbacks__path_key__startswith'] = path_key
        return Form.objects.all().filter(**filters)

    def get_latest_form(self, path_key=None, max_age=None):
        forms = self.get_forms(path_key)
        if max_age:
            forms = forms.filter(feedbacks__timestamp__gt=timezone.now()-max_age)
        try:
            return forms.latest('feedbacks__timestamp')
        except Form.DoesNotExist:
            return None

    @property
    def unresponded_feedback(self):
        return Feedback.objects.get_notresponded(exercise_id=self.id)

    def __str__(self):
        return self.display_name


class FeedbackManager(models.Manager):
    def feedback_exercises_for(self, student):
        F = models.F
        key = 'student' if isinstance(student, Student) else 'student_id'
        q = self.values(
                'exercise_id',
            ).filter(
                **{key: student}
            ).annotate(
                course_id=F('exercise__course__id'),
                count=models.Count('form_data'),
            ).order_by(
                'course_id', 'exercise_id'
            )
        return q

    def get_notresponded(self, exercise_id=None, course_id=None, path_filter=None):
        Q = models.Q
        qs = self.get_queryset().select_related(
            'form',
            'exercise',
        ).all().filter(
            Q(response_msg='') | Q(response_msg=None),
            superseded_by=None,
        ).exclude(
            submission_url='',
        )
        if exercise_id is not None:
            qs = qs.filter(exercise__id=exercise_id)
        elif course_id is not None:
            qs = qs.filter(exercise__course__id=course_id)
            if path_filter:
                qs = qs.filter(path_key__startswith=path_filter)
        else:
            raise ValueError("exercise_id or course_id is required")
        return qs.order_by('timestamp')


ResponseUploaded = namedtuple('ResponseUploaded',
                              ('ok', 'when', 'code', 'attempts'))


class Feedback(models.Model):
    objects = FeedbackManager()

    GRADES = Enum(
        ('NONE', -1, _('No response')), # can't be stored in db (positive integers only)
        ('REJECTED', 0, _('Rejected')),
        ('ACCEPTED', 1, _('Accepted')),
        ('ACCEPTED_GOOD', 2, _('Good')),
    )
    MAX_GRADE = GRADES.ACCEPTED_GOOD
    OK_GRADES = (GRADES.ACCEPTED, GRADES.ACCEPTED_GOOD)

    exercise = models.ForeignKey(Exercise,
                                 related_name='feedbacks',
                                 on_delete=models.PROTECT)
    path_key = models.CharField(max_length=255, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now)
    language = models.CharField(max_length=5, default=get_language, null=True)
    student = models.ForeignKey(Student,
                                related_name='feedbacks',
                                on_delete=models.CASCADE,
                                db_index=True)
    form = models.ForeignKey(Form,
                             related_name='feedbacks',
                             on_delete=models.PROTECT,
                             null=True)
    form_data = pg_fields.JSONField(blank=True)
    superseded_by = models.ForeignKey('self',
                                      related_name="supersedes",
                                      on_delete=models.SET_NULL,
                                      null=True,
                                      db_index=True)
    post_url = models.URLField()
    submission_url = models.URLField()
    response_msg = models.TextField(blank=True,
                                    null=True,
                                    default=None,
                                    verbose_name="Response")
    response_grade = models.PositiveSmallIntegerField(default=GRADES.REJECTED,
                                                      choices=[x for x in GRADES.choices if x[0] >= 0],
                                                      verbose_name="Grade")
    _response_time = models.DateTimeField(null=True,
                                          db_column='response_time')
    _response_upl_code = models.PositiveSmallIntegerField(default=0,
                                                          db_column='response_upload_code')
    _response_upl_attempt = models.PositiveSmallIntegerField(default=0,
                                                             db_column='response_upload_attempt')
    _response_upl_at = models.DateTimeField(null=True,
                                            db_column='response_upload_at')

    RESPONSE_FIELDS =  (
        'response_msg',
        'response_grade',
    )
    RESPONSE_EXTRA_FIELDS = (
        '_response_time',
        '_response_upl_code',
        '_response_upl_attempt',
        '_response_upl_at',
    )

    @cached_property
    def course(self):
        return self.exercise.course

    @cached_property
    def exercise_path(self):
        return "{}{}{}".format(
            self.exercise,
            "/" if self.path_key else "",
            self.path_key or '',
        )

    @property
    def form_class(self):
        return self.form.form_class

    @property
    def form_obj(self):
        return self.form_class(data=self.form_data)

    @property
    def response_time(self):
        return self._response_time

    @property
    def response_uploaded(self):
        when = self._response_upl_at
        code = self._response_upl_code
        attempts = self._response_upl_attempt
        ok = code == 200
        return ResponseUplaoded(ok, when, code, attempts)

    @response_uploaded.setter
    def response_uploaded(self, status_code):
        self._response_upl_code = status_code
        self._response_upl_attempt += 1
        self._response_upl_at = timezone.now()

    @property
    def responded(self):
        return self._response_time is not None

    @property
    def response_grade_text(self):
        if not self.responded:
            return self.GRADES[self.GRADES.NONE]
        return self.GRADES[self.response_grade]

    @property
    def valid_response_grade(self):
        if not self.responded:
            return None
        return self.response_grade

    @classmethod
    @transaction.atomic
    def create_new_version(cls, **kwargs):
        """
        Creates new feedback object and marks it as parent for all
        old feedbacks by same user to defined resource
        """
        # create new item
        new = cls.objects.create(**kwargs)
        assert new.pk is not None, "New feedback doesn't have primary key"

        # mark all old versions to be superseded_by this new
        current_versions = cls.objects.all().filter(
            ~models.Q(pk=new.pk),
            superseded_by = None,
            form = new.form,
            student = new.student,
        ).update(superseded_by=new)

        return new

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__response = {k: getattr(self, k) for k in self.RESPONSE_FIELDS}

    def clean(self):
        # if response field is changed set udpate time
        for k in self.RESPONSE_FIELDS:
            if getattr(self, k) != self.__response[k]:
                self._response_time = timezone.now()
                break

    def save(self, update_fields=None, **kwargs):
        response_update = True
        if update_fields is not None:
            update_fields = set(update_fields)
            if any(k in update_fields for k in self.RESPONSE_FIELDS):
                update_fields.update(self.RESPONSE_FIELDS)
                update_fields.update(self.RESPONSE_EXTRA_FIELDS)
            else:
                response_update = False
            update_fields = tuple(update_fields)
        ret = super().save(update_fields=update_fields, **kwargs)
        if response_update:
            self.__response = {k: getattr(self, k) for k in self.RESPONSE_FIELDS}
        return ret

    @property
    def can_be_responded(self):
        return self.submission_url and not self.superseded_by_id

    @cached_property
    def has_older_versions(self):
        return self.supersedes.exists()

    def __getitem__(self, key):
        return self.feedback[key]

    def __setitem__(self, key, value):
        self.feedback[key] = value
