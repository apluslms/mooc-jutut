import datetime
from django.db import models
from django.contrib.postgres import fields as pg_fields
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

class FormManager(models.Manager):
    def latest_for(self, **filters):
        try:
            return self.all().filter(**filters).latest()
        except ObjectDoesNotExist:
            return None

    def get_or_create(self, form_spec, **filters):
        form = self.latest_for(**filters)
        if not form or form.form_spec != form_spec:
            form = self.create(form_spec=form_spec, **filters)
        return form


class FormBase(models.Model):
    objects = FormManager()

    TTL = datetime.timedelta(hours=1)

    class Meta:
        abstract = True
        get_latest_by = 'updated'

    form_spec = pg_fields.JSONField()
    updated = models.DateTimeField(default=timezone.now)

    @property
    def could_be_updated(self):
        age = timezone.now() - self.updated
        return age > self.TTL

    def get_updated(self, form_spec, **extra):
        if not form_spec:
            return self

        if self.form_spec == form_spec:
            self.updated = timezone.now()
            self.save()
            return self

        new = self.__class__(form_spec=form_spec, **extra)
        new.save()
        return new
