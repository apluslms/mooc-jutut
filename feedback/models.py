import datetime
from django.db import models, transaction
from django.contrib.postgres import fields as pg_fields


class Feedback(models.Model):
    timestamp = models.DateTimeField(default=datetime.datetime.now)
    course_id = models.IntegerField(db_index=True)
    group_path = models.CharField(max_length=255, db_index=True)
    user_id = models.IntegerField(db_index=True)
    form_data = pg_fields.JSONField(blank=True)
    superseded_by = models.OneToOneField('self', null=True, db_index=True)
    response = models.TextField(blank=True)

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

    def __getitem__(self, key):
        return self.feedback[key]

    def __setitem__(self, key, value):
        self.feedback[key] = value
