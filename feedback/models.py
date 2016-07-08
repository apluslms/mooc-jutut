import datetime
from django.db import models, transaction
from django.contrib.postgres import fields as pg_fields
from django.utils import timezone
from django.utils.functional import cached_property

class FeedbackManager(models.Manager):
    def feedback_groups_for(self, student):
        key = 'student_id' if type(student) is int else 'student'
        q = ( self.values('course_id', 'group_path')
                  .filter(**{key: student})
                  .annotate(count=models.Count('form_data'))
                  .order_by('group_path') )
        return q

class Feedback(models.Model):
    objects = FeedbackManager()

    timestamp = models.DateTimeField(default=timezone.now)
    course_id = models.IntegerField(db_index=True)
    group_path = models.CharField(max_length=255, db_index=True)
    student = models.ForeignKey('Student',
                                related_name='feedbacks',
                                on_delete=models.CASCADE,
                                db_index=True)
    form_data = pg_fields.JSONField(blank=True)
    superseded_by = models.ForeignKey('self',
                                      related_name="supersedes",
                                      on_delete=models.SET_NULL,
                                      null=True,
                                      db_index=True)
    submission_url = models.URLField(blank=True)
    response = models.TextField(blank=True)
    response_time = models.DateTimeField(null=True)

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
        self.__response = self.response

    def save(self, update_fields=None, **kwargs):
        if self.__response != self.response:
            self.response_time = timezone.now()
            if update_fields and 'response' in update_fields:
                update_fields = list(update_fields)
                update_fields.append('response_time')
        return super().save(update_fields=update_fields, **kwargs)

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
