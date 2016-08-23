import datetime
from collections import namedtuple
from django.db import models, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.postgres import fields as pg_fields
from django.utils import timezone
from django.utils.functional import cached_property

from aplus_client.django.models import CachedApiObject
from dynamic_forms.models import FormBase


class Student(CachedApiObject):
    username = models.CharField(max_length=128)
    full_name = models.CharField(max_length=128)

    def __str__(self):
        return "{s.full_name:s} ({s.username:s})".format(s=self)


class Course(CachedApiObject):
    code = models.CharField(max_length=128)
    name = models.CharField(max_length=128)

    def __str__(self):
        return "{s.code:s} - {s.name:s}".format(s=self)


class ExerciseManager(models.Manager):
    def with_course(self):
        return super().get_queryset().select_related('course')


class Exercise(CachedApiObject):
    objects = ExerciseManager()

    display_name = models.CharField(max_length=255)
    course = models.ForeignKey(Course,
                               related_name='exercises',
                               on_delete=models.PROTECT)

    @property
    def feedbacks(self):
        return Feedback.objects.filter(form__exercise=self)

    @property
    def unresponded_feedback(self):
        return Feedback.objects.get_unresponded(exercise_id=self.id)

    @cached_property
    def latest_form(self):
        try:
            return self.forms.latest()
        except ObjectDoesNotExist:
            return None

    def __str__(self):
        return self.display_name


class Form(FormBase):
    # our grouping in top of base form storage
    exercise = models.ForeignKey(Exercise,
                                related_name='forms',
                                on_delete=models.PROTECT)

    TTL = datetime.timedelta(minutes=10)

    def get_updated(self, form_spec):
        return super().get_updated(
            form_spec=form_spec,
            course_id=self.course_id,
            exercise_id=self.exercise_id,
        )


class FeedbackManager(models.Manager):
    def feedback_exercises_for(self, student):
        F = models.F
        key = 'student_id' if type(student) is int else 'student'
        q = self.values(
                'path_key',
            ).filter(
                **{key: student}
            ).annotate(
                course_id=F('form__exercise__course__id'),
                exercise_id=F('form__exercise__id'),
                count=models.Count('form_data'),
            ).order_by(
                'course_id', 'exercise_id', 'path_key'
            )
        return q

    def get_unresponded(self, exercise_id=None, course_id=None, path_filter=None):
        Q = models.Q
        qs = self.get_queryset().select_related(
            'form',
            'form__exercise',
            #'form__exercise__course',
        ).all().filter(
            Q(response_msg='') | Q(response_msg=None),
            superseded_by=None,
        ).exclude(
            submission_url='',
        )
        if exercise_id is not None:
            qs = qs.filter(form__exercise__id=exercise_id)
        elif course_id is not None:
            qs = qs.filter(form__exercise__course__id=course_id)
            if path_filter:
                qs = qs.filter(path_key__startswith=path_filter)
        else:
            raise ValueError("exercise_id or course_id is required")
        return qs.order_by('timestamp')


ResponseUploaded = namedtuple('ResponseUploaded',
                              ('ok', 'when', 'code', 'attempts'))


class Feedback(models.Model):
    objects = FeedbackManager()

    REJECTED = 0
    ACCEPTED = 1
    ACCEPTED_GOOD = 2
    GRADES = {
        REJECTED: 'Rejected',
        ACCEPTED: 'Accepted',
        ACCEPTED_GOOD: 'Accepted and Good',
    }
    MAX_GRADE = ACCEPTED_GOOD

    path_key = models.CharField(max_length=255, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now)
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
    response_grade = models.PositiveSmallIntegerField(default=REJECTED,
                                                      choices=GRADES.items(),
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
    def exercise(self):
        return self.form.exercise

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
        return self.GRADES.get(self.response_grade)

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
