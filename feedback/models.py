import datetime
from django.db import models
from django.contrib.postgres import fields as pg_fields


class Feedback(models.Model):
    timestamp = models.DateTimeField(default=datetime.datetime.now)
    course_id = models.IntegerField(db_index=True)
    group_path = models.CharField(max_length=255, db_index=True)
    user_id = models.IntegerField(db_index=True)
    form_data = pg_fields.JSONField(blank=True)
    superseded_by = models.OneToOneField('self', null=True)
    response = models.TextField(blank=True)


    def __getitem__(self, key):
        return self.feedback[key]

    def __setitem__(self, key, value):
        self.feedback[key] = value
