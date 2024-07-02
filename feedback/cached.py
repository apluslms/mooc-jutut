from typing import Optional

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from aplus_client.client import AplusTokenClient

from .models import (
    Site,
    Course,
    Student,
    Feedback,
    FeedbackForm,
    FeedbackTag,
)
from .background_helpers import (
    get_bg_questionnaires,
    get_student_bg_responses,
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
def post_site_save(sender, **kwargs): # pylint: disable=unused-argument
    CachedSites.clear()


class CachedCourses(Cached):
    def get_suffix(self, site): # pylint: disable=arguments-differ
        return site.id

    def get_obj(self, site):
        return list(Course.objects.using_namespace_id(site.id).all())


CachedCourses = CachedCourses()

@receiver(post_save, sender=Course)
def post_course_save(sender, instance, **kwargs): # pylint: disable=unused-argument
    course = instance
    CachedCourses.clear(course.namespace)


class CachedNotrespondedCount(Cached):
    def get_suffix(self, course): # pylint: disable=arguments-differ
        return course.id

    def get_obj(self, course):
        return Feedback.objects.get_notresponded(course_id=course.id).count()


CachedNotrespondedCount = CachedNotrespondedCount(timeout=60*10)

@receiver(post_save, sender=Feedback)
def notresponded_post_feedback_save(sender, instance, **kwargs): # pylint: disable=unused-argument
    feedback = instance
    CachedNotrespondedCount.clear(feedback.exercise.course)

@receiver(m2m_changed, sender=FeedbackTag.conversations.through)
# pylint: disable-next=unused-argument
def notresponded_post_feedback_tag_change(sender, instance, action, reverse, **kwargs):
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    course = instance.exercise.course if reverse else instance.course
    CachedNotrespondedCount.clear(course)


class CachedTags(Cached):
    def get_suffix(self, course): # pylint: disable=arguments-differ
        return course.id

    def get_obj(self, course):
        return list(course.tags.all())


CachedTags = CachedTags()

@receiver(post_save, sender=FeedbackTag)
def post_tag_save(sender, instance, **kwargs): # pylint: disable=unused-argument
    tag = instance
    CachedTags.clear(tag.course)

@receiver(post_delete, sender=FeedbackTag)
def post_tag_delete(sender, instance, **kwargs): # pylint: disable=unused-argument
    tag = instance
    CachedTags.clear(tag.course)


class CachedForm(Cached):
    def get_suffix(self, key, spec_getter=None, i18n_getter=None): # pylint: disable=arguments-differ unused-argument
        return key

    def get_obj(self, key, spec_getter, i18n_getter): # pylint: disable=unused-argument
        form_spec = spec_getter()
        form_i18n = i18n_getter()
        if form_spec is None:
            raise ValueError("spec_getter returned None")
        try:
            return FeedbackForm.objects.get_or_create(form_spec=form_spec, form_i18n=form_i18n)
        except ValidationError as e:
            raise ValueError("spec_getter returned invalid form_spec: %s" % (e,)) from e


CachedForm = CachedForm(timeout=60*60)


class MiscCache:
    """Cache for storing miscellaneous content related to a course."""
    def __init__(self, prefix=None, timeout=None) -> None:
        self.prefix = prefix or self.__class__.__name__
        self.timeout = timeout or 60 * 60

    def get_suffix(self, *args) -> str:
        return '-'.join(str(x) for x in args)

    def get(self, key: str, course: Course) -> object:
        full_key = '/'.join((self.prefix, self.get_suffix(key, course.id)))
        return cache.get(full_key)

    def set(self, key: str, course: Course, value, timeout=-1) -> None:
        full_key = '/'.join((self.prefix, self.get_suffix(key, course.id)))
        timeout = timeout if (timeout != -1) else self.timeout
        cache.set(full_key, value, timeout)


class BackgroundCache(MiscCache):
    """Cache for storing information about background questionnaires.
    Stores both background questionnaire (enrollment exercise) api ids with
    with relevant information (such as question types, display texts, etc.)
    as well as student responses to questionnaires.
    """
    def get_bg_questionnaires(self, course: Course)-> Optional[dict[int, dict]]:
        return self.get('questionnaires', course)

    def get_or_set_bg_questionnaires(self,
            course: Course,
            client: AplusTokenClient
            ) -> dict[int, dict]:
        bgq_dict = self.get_bg_questionnaires(course)
        if bgq_dict is None: # not saved in cache yet
            bgq_dict = get_bg_questionnaires(course, client)
            # set in cache
            self.set('questionnaires', course, bgq_dict)
        return bgq_dict

    def get_response(self, student: Student, course: Course) -> Optional[tuple[int, dict]]:
        full_key = '/'.join((
            self.prefix,
            self.get_suffix(student.id, course.id, 'response'),
        ))
        return cache.get(full_key)

    def get_or_set_response(self,
            student: Student,
            course: Course,
            client: AplusTokenClient
            ) -> tuple[int, dict]:
        response = self.get_response(student, course)
        if response is None: # not saved in cache yet
            bg_questionnaires = self.get_or_set_bg_questionnaires(course, client)
            if len(bg_questionnaires) == 0:
                # no background questionnaires on course
                response = (None, None)
            else:
                response = get_student_bg_responses(
                    student, client, bg_questionnaires
                )
            # set value in cache
            full_key = '/'.join((
                self.prefix,
                self.get_suffix(student.id, course.id, 'response'),
            ))
            cache.set(full_key, response)
        return response


BackgroundCache = BackgroundCache(timeout=60*60*24*120) #120 days

MiscCache = MiscCache()
