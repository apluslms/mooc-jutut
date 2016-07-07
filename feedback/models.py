import datetime
from django.db import models, transaction
from django.contrib.postgres import fields as pg_fields
from django.utils.functional import cached_property


class Feedback(models.Model):
    timestamp = models.DateTimeField(default=datetime.datetime.now)
    course_id = models.IntegerField(db_index=True)
    group_path = models.CharField(max_length=255, db_index=True)
    user_id = models.IntegerField(db_index=True)
    form_data = pg_fields.JSONField(blank=True)
    superseded_by = models.ForeignKey('self',
                                      related_name="supersedes",
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
            user_id = kwargs['user_id'],
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
            self.response_time = datetime.datetime.now()
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
