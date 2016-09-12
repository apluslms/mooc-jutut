from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    Site,
    Course,
    Feedback,
)

class Cached:
    def __init__(self, prefix=None, timeout=None):
        self.prefix = prefix or self.__class__.__name__
        self.timeout = timeout or 60 * 5

    def get_suffix(self, key_obj):
        return key_obj

    def get(self, key_obj):
        key = self.prefix + str(self.get_suffix(key_obj))
        obj = cache.get(key)
        if obj is None:
            obj = self.get_obj(key_obj)
            cache.set(key, obj, self.timeout)
        return obj

    def clear(self, key_obj):
        key = self.prefix + str(self.get_suffix(key_obj))
        cache.delete(key)


class CachedSites(Cached):
    def get_obj(self, suffix):
        return list(Site.objects.all())

    def get(self):
        return super().get('')

    def clear(self):
        super().clear('')
CachedSites = CachedSites()

@receiver(post_save, sender=Site)
def post_site_save(sender, **kwargs):
    CachedSites.clear()


class CachedCourses(Cached):
    def get_obj(self, site):
        return list(Course.objects.using_namespace_id(site.id).all())

    def get_suffix(self, site):
        return site.id
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
CachedNotrespondedCount = CachedNotrespondedCount()

@receiver(post_save, sender=Feedback)
def post_course_save(sender, instance, **kwargs):
    feedback = instance
    CachedNotrespondedCount.clear(feedback.exercise.course)
