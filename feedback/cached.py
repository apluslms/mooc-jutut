from django.core.cache import cache
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from .models import (
    Site,
    Course,
    Feedback,
    FeedbackForm,
    FeedbackTag,
)


class FormCache:
    """
    Short time buffer for feedback form classes
    """
    def __init__(self):
        self.cache = {}

    def get(self, feedback):
        cache = self.cache
        form_id = feedback.form_id
        form_class = cache.get(form_id)
        if not form_class:
            form_class = feedback.get_form_class(True)
            cache[form_id] = form_class
        return form_class(data=feedback.form_data)


class Cached:
    def __init__(self, prefix=None, timeout=None):
        self.prefix = prefix or self.__class__.__name__
        self.timeout = timeout or 60 * 60

    def get_suffix(self, *args):
        return '-'.join(str(x) for x in args)

    def get(self, *args):
        key = '/'.join((self.prefix, str(self.get_suffix(*args))))
        obj = cache.get(key)
        if obj is None:
            obj = self.get_obj(*args)
            cache.set(key, obj, self.timeout)
        return obj

    def clear(self, *args):
        key = '/'.join((self.prefix, str(self.get_suffix(*args))))
        cache.delete(key)


class CachedSites(Cached):
    def get_obj(self):
        return list(Site.objects.all())
CachedSites = CachedSites()

@receiver(post_save, sender=Site)
def post_site_save(sender, **kwargs):
    CachedSites.clear()


class CachedCourses(Cached):
    def get_suffix(self, site):
        return site.id

    def get_obj(self, site):
        return list(Course.objects.using_namespace_id(site.id).all())
CachedCourses = CachedCourses()

@receiver(post_save, sender=Course)
def post_course_save(sender, instance, **kwargs):
    course = instance
    CachedCourses.clear(course.namespace)


class CachedNotrespondedCount(Cached):
    def get_suffix(self, course):
        return course.id

    def get_obj(self, course):
        return Feedback.objects.get_notresponded(course_id=course.id).count()
CachedNotrespondedCount = CachedNotrespondedCount(timeout=60*10)

@receiver(post_save, sender=Feedback)
def notresponded_post_feedback_save(sender, instance, **kwargs):
    feedback = instance
    CachedNotrespondedCount.clear(feedback.exercise.course)

@receiver(m2m_changed, sender=FeedbackTag.feedbacks.through)
def notresponded_post_feedback_tag_change(sender, instance, action, reverse, **kwargs):
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    course = instance.exercise.course if reverse else instance.course
    CachedNotrespondedCount.clear(course)


class CachedTags(Cached):
    def get_suffix(self, course):
        return course.id

    def get_obj(self, course):
        return list(course.tags.all())
CachedTags = CachedTags()

@receiver(post_save, sender=FeedbackTag)
def post_tag_save(sender, instance, **kwargs):
    tag = instance
    CachedTags.clear(tag.course)


class CachedForm(Cached):
    def get_suffix(self, key, spec_getter, i18n_getter):
        return key

    def get_obj(self, key, spec_getter, i18n_getter):
        form_spec = spec_getter()
        form_i18n = i18n_getter()
        if form_spec is None:
            raise ValueError("spec_getter returned None")
        return FeedbackForm.objects.get_or_create(form_spec=form_spec, form_i18n=form_i18n)
CachedForm = CachedForm(timeout=60*60)
