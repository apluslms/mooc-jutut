import logging
from django.apps import apps
from django.contrib.postgres import fields as pg_fields
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from .forms import DynamicForm, DummyForm
from .utils import bytefy, freeze_digest

logger = logging.getLogger('dynamic_forms.models')


class FormManager(models.Manager):
    def get_or_create(self, form_spec, form_i18n):
        frozen_spec = bytefy(form_spec)
        frozen_i18n = bytefy(form_i18n)
        sha = freeze_digest(frozen_spec, frozen_i18n)
        obj = None

        # find if this form_spec exists already
        for possible in self.filter(sha1=sha):
            if possible.form_spec == form_spec and possible.form_i18n == form_i18n:
                obj = possible
                break

        # create new database object and save it
        if not obj:
            obj = self.create(form_spec=form_spec, form_i18n=form_i18n, sha1=sha)

        # store already calculated frozen_spec
        obj.frozen_spec = frozen_spec
        obj.frozen_i18n = frozen_i18n
        return obj


class Form(models.Model):
    objects = FormManager()

    sha1 = models.CharField(max_length=40, db_index=True)
    form_spec = pg_fields.JSONField()
    form_i18n = pg_fields.JSONField(blank=True, null=True)

    class Meta:
        abstract = apps.get_containing_app_config(__name__) is None
        ordering = ('id',)
        verbose_name = _("Form")
        verbose_name_plural = _("Forms")

    @cached_property
    def frozen_spec(self):
        return bytefy(self.form_spec)

    @cached_property
    def frozen_i18n(self):
        return bytefy(self.form_i18n)

    @cached_property
    def form_class(self):
        return DynamicForm.get_form_class_by(self)

    @cached_property
    def form_class_or_dummy(self):
        try:
            return self.form_class
        except ValueError as error:
            logger.critical("DB has invalid form_spec with id %d: %s", self.id, error)
            return DummyForm

    def save(self, **kwargs):
        if not self.sha1:
            frozen_spec = bytefy(self.form_spec)
            frozen_i18n = bytefy(self.form_i18n)
            self.sha1 = freeze_digest(frozen_spec, frozen_i18n)
        return super().save(**kwargs)

    def __str__(self):
        return "<Form {}, {} fields, sha1:{}>".format(self.pk, len(self.form_spec), self.sha1)
