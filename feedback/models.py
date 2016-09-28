import datetime
import shlex
from collections import namedtuple
from functools import reduce
from django.db import models, transaction
from django.conf import settings
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

Q = models.Q


class StudentManager(NamespacedApiObject.Manager):
    def get_students_on_course(self, course):
        return ( self.using_namespace_id(course.namespace_id)
                 .filter(feedbacks__exercise__course=course)
                 .distinct()
                 .all() )


class Student(NamespacedApiObject):
    objects = StudentManager()

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

    @property
    def unresponded_feedback(self):
        return Feedback.objects.get_notresponded(exercise_id=self.id)

    def __str__(self):
        return self.display_name


class FeedbackQuerySet(models.QuerySet):
    FILTER_FLAGS = Enum(
        ('NEWEST', 'n', _("Newest versions")),
        ('UNREAD', 'u', _("Unread")),
        ('READ', 'r', _("Read")),
        ('GRADED', 'g', _("Graded")),
        ('AUTO', 'a', _("Automatically graded")),
        ('MANUAL', 'm', _("Manually graded")),
        ('RESPONDED', 'h', _("Responded")),
        ('UPL_OK', 'o', _("Upload ok")),
        ('UPL_ERROR', 'e', _("Upload has error")),
    )

    FILTERS = {
        FILTER_FLAGS.NEWEST: Q(superseded_by=None),
        FILTER_FLAGS.UNREAD: Q(response_time=None),
        FILTER_FLAGS.READ: ~Q(response_time=None),
        FILTER_FLAGS.GRADED: ~Q(response_time=None),
        FILTER_FLAGS.RESPONDED: ~Q(response_time=None) & ~Q(response_msg='') & ~Q(response_msg=None),
        FILTER_FLAGS.AUTO: ~Q(response_time=None) & Q(response_by=None),
        FILTER_FLAGS.MANUAL: ~Q(response_time=None) & ~Q(response_by=None),
        FILTER_FLAGS.UPL_OK: Q(_response_upl_code=200),
        FILTER_FLAGS.UPL_ERROR: ~Q(_response_upl_code=200) & ~Q(_response_upl_code=0),
    }

    def filter_flags(self, *flags):
        try:
            filters = [self.FILTERS[f] for f in flags]
        except KeyError as e:
            raise AttributeError("Invalid flag: {}".format(e))
        q = reduce(Q.__and__, filters)
        return self.filter(q)

    def filter_data(self, search):
        if '*' in search:
            search = search.replace('*', '%')
        else:
            search = ''.join(('%', '%'.join(shlex.split(search)), '%'))
        return self.extra(
            where=['form_data::text ilike %s'],
            params=[search],
        )

    def feedback_exercises_for(self, course, student):
        q = self.values(
                'exercise_id',
                'path_key',
            ).filter(
                student=student,
                exercise__course=course,
            ).annotate(
                count=models.Count('form_data'),
            ).order_by(
                'exercise__course', 'exercise_id'
            )
        return q

    def get_notresponded(self, exercise_id=None, course_id=None, path_filter=None):
        qs = self.select_related('form', 'exercise').filter_flags(
            self.FILTER_FLAGS.NEWEST,
            self.FILTER_FLAGS.UNREAD,
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
    objects = FeedbackQuerySet.as_manager()

    class Meta:
        unique_together = [
            ('exercise', 'submission_id'),
        ]

    GRADES = Enum(
        ('NONE', -1, _('No response')), # can't be stored in db (positive integers only)
        ('REJECTED', 0, _('Rejected')),
        ('ACCEPTED', 1, _('Accepted')),
        ('ACCEPTED_GOOD', 2, _('Good')),
    )
    GRADE_CHOICES = [x for x in GRADES.choices if x[0] >= 0]
    MAX_GRADE = GRADES.ACCEPTED_GOOD
    OK_GRADES = (GRADES.ACCEPTED, GRADES.ACCEPTED_GOOD)

    # identifier
    exercise = models.ForeignKey(Exercise,
                                 related_name='feedbacks',
                                 on_delete=models.PROTECT)
    submission_id = models.IntegerField()
    path_key = models.CharField(max_length=255, db_index=True)

    # feedback
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    language = models.CharField(max_length=5, default=get_language, null=True)
    student = models.ForeignKey(Student,
                                related_name='feedbacks',
                                on_delete=models.CASCADE)
    form = models.ForeignKey(Form,
                             related_name='feedbacks',
                             on_delete=models.PROTECT,
                             null=True)
    form_data = pg_fields.JSONField(blank=True)
    superseded_by = models.ForeignKey('self',
                                      related_name="supersedes",
                                      on_delete=models.SET_NULL,
                                      null=True)
    post_url = models.URLField()
    submission_url = models.URLField()
    submission_html_url = models.URLField()

    # response
    response_time = models.DateTimeField(null=True)
    response_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    related_name='responded_feedbacks',
                                    on_delete=models.SET_NULL,
                                    null=True)
    response_msg = models.TextField(blank=True,
                                    null=True,
                                    default=None,
                                    verbose_name="Response")
    response_grade = models.PositiveSmallIntegerField(default=GRADES.REJECTED,
                                                      choices=GRADE_CHOICES,
                                                      verbose_name="Grade")

    # response upload
    _response_upl_code = models.PositiveSmallIntegerField(default=0,
                                                          db_column='response_upload_code')
    _response_upl_attempt = models.PositiveSmallIntegerField(default=0,
                                                             db_column='response_upload_attempt')
    _response_upl_at = models.DateTimeField(null=True,
                                            db_column='response_upload_at')


    # Extra getters and properties

    @cached_property
    def course(self):
        return self.exercise.course

    @staticmethod
    def get_exercise_path(exercise, path_key):
        return "{}{}{}".format(
            exercise,
            "/" if path_key else "",
            path_key or '',
        )

    @cached_property
    def exercise_path(self):
        return self.get_exercise_path(self.exercise, self.path_key)

    @property
    def form_class(self):
        return self.form.form_class

    def get_form_class(self, dummy=True):
        return self.form.form_class_or_dummy if dummy else self.form.form_class

    @property
    def form_obj(self):
        return self.form_class(data=self.form_data)

    def get_form_obj(self, dummy=False):
        return self.get_form_class(dummy)(data=self.form_data)

    @property
    def response_uploaded(self):
        when = self._response_upl_at
        code = self._response_upl_code
        attempts = self._response_upl_attempt
        ok = code in (0, 200)
        return ResponseUploaded(ok, when, code, attempts)

    @response_uploaded.setter
    def response_uploaded(self, status_code):
        if status_code:
            self._response_upl_code = status_code
            self._response_upl_attempt += 1
            self._response_upl_at = timezone.now()
        else:
            self._response_upl_code = 0
            self._response_upl_attempt = 0
            self._response_upl_at = None
        self.__changed_fields.update(('_response_upl_code', '_response_upl_attempt', '_response_upl_at'))

    @property
    def responded(self):
        return self.response_time is not None

    @property
    def waiting_for_response(self):
        return not self.responded and not self.superseded_by_id

    @property
    def can_be_responded(self):
        return bool(self.submission_url)

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

    @property
    def older_versions(self):
        return self.__class__.objects.filter(
            ~models.Q(pk=self.pk),
            exercise_id = self.exercise_id,
            student_id = self.student_id,
            timestamp__lt = self.timestamp,
        )

    @cached_property
    def older_versions_count(self):
        return self.older_versions.count()

    def __getitem__(self, key):
        return self.feedback[key]

    def __setitem__(self, key, value):
        self.feedback[key] = value


    # Feedback management interface

    @classmethod
    @transaction.atomic
    def create_new_version(cls, **kwargs):
        """
        Creates new feedback object and marks it as parent for all
        old feedbacks by same user to defined resource
        """
        kwargs = {k: v for k,v in kwargs.items() if v is not None}
        new = cls.objects.create(**kwargs)
        assert new.pk is not None, "New feedback doesn't have primary key"
        new.supersede_older()
        return new

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__changed_fields = set()

    def __str__(self):
        return 'Feedback by {} to {} at {}'.format(
            self.student, self.exercise_path, self.timestamp
        )

    def save(self, update_fields=None, **kwargs):
        if update_fields is not None and self.__changed_fields:
            update_fields = tuple(set(update_fields) | self.__changed_fields)
        ret = super().save(update_fields=update_fields, **kwargs)
        self.__changed_fields = set()
        return ret

    def supersede_older(self):
        return self.older_versions.filter(
            superseded_by = None,
        ).update(superseded_by=self)
