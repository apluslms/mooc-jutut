import datetime
from collections import namedtuple
from django.db import models, transaction
from django.contrib.postgres import fields as pg_fields
from django.utils import timezone
from django.utils.functional import cached_property

from dynamic_forms.models import FormBase

class Form(FormBase):
    # our grouping in top of base form storage
    course_id = models.IntegerField(db_index=True)
    group_path = models.CharField(max_length=255, db_index=True)

    TTL = datetime.timedelta(minutes=10)

    def update(self, form_spec):
        return super().update(
            form_spec=form_spec,
            course_id=self.course_id,
            group_path=self.group_path,
        )


class FeedbackManager(models.Manager):
    def feedback_groups_for(self, student):
        key = 'student_id' if type(student) is int else 'student'
        q = ( self.values('course_id', 'group_path')
                  .filter(**{key: student})
                  .annotate(count=models.Count('form_data'))
                  .order_by('group_path') )
        return q


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

    timestamp = models.DateTimeField(default=timezone.now)
    course_id = models.IntegerField(db_index=True)
    group_path = models.CharField(max_length=255, db_index=True)
    student = models.ForeignKey('Student',
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
        # there should be only single current version, but
        # to be sure we presume there might be multiple
        current_versions = list(cls.objects.all().filter(
            superseded_by = None,
            course_id = kwargs['course_id'],
            group_path = kwargs['group_path'],
            student = kwargs['student'],
        ))
        new = cls(**kwargs)
        # save new feedback, so it will have id
        new.save()
        # mark new one as top version for other version
        for old in current_versions:
            old.superseded_by = new
            old.save()
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


class Student(models.Model):
    user_id = models.IntegerField(primary_key=True)
    url = models.URLField()
    updated = models.DateTimeField(auto_now=True)

    username = models.CharField(max_length=64)
    full_name = models.CharField(max_length=64)


    @classmethod
    def create_or_update(cls, user):
        obj, created = cls.objects.get_or_create(user_id=user.user_id)
        if created or obj.should_be_updated:
            obj.update_with(user)
        return obj

    @property
    def should_be_updated(self):
        age = timezone.now() - self.updated
        return age > datetime.timedelta(hours=1)

    def update_with(self, data):
        print("Updating user with data:", data)
        if not self.url:
            self.url = data.url
        self.username = data.username
        self.full_name = data.full_name
        self.save()

    def __str__(self):
        return "%s (%d)" % (self.full_name, self.user_id)
