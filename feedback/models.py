import datetime
import re
import shlex

from collections import namedtuple
from functools import reduce

from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import get_language, gettext_lazy as _
from django_colortag.models import ColorTag
from r_django_essentials.fields import Enum

from aplus_client.django.models import (
    ApiNamespace as Site, # mooc-jutut refers api namespaces as sites
    NamespacedApiObject,
    NestedApiObject,
)
from dynamic_forms.models import Form

from .forms_dynamic import DynamicFeedbacForm

Q = models.Q


class FeedbackForm(Form):
    class Meta:
        proxy = True

    @cached_property
    def form_class(self):
        return DynamicFeedbacForm.get_form_class_by(self)



class StudentManager(NamespacedApiObject.Manager):
    def get_students_on_course(self, course):
        return ( self.using_namespace_id(course.namespace_id)
                 .filter(feedbacks__exercise__course=course)
                 .distinct()
                 .all() )

    def get_students_on_courses(self, courses):
        return ( self.all()
                 .filter(feedbacks__exercise__course__in=courses)
                 .distinct() )


class Student(NamespacedApiObject):
    objects = StudentManager()

    username = models.CharField(max_length=128)
    full_name = models.CharField(max_length=128)
    student_id = models.CharField(max_length=25, null=True, blank=True)
    tags = models.ManyToManyField('StudentTag', related_name="students")

    def __str__(self):
        extra = ", {}".format(self.student_id) if self.student_id else ""
        return "{:s} ({:s}{})".format(self.full_name, self.username, extra)


class StudentTag(NamespacedApiObject, ColorTag):
    course = models.ForeignKey('Course',
                                related_name="student_tags",
                                on_delete=models.CASCADE)

    @classmethod
    def update_from_api(cls, client, course):
        course_api = client.load_data(course.url)
        new_tags = set()
        tags = {}
        students = {}
        taggings = {}

        # Ensure all tags and students exist, and collect taggings
        for tagging in course_api.get("taggings", ignore_cache=True):
            tag = tags.get(tagging.tag.id)
            if not tag:
                tag, created = cls.objects.get_new_or_updated(tagging.tag, course=course)
                if created:
                    new_tags.add(tag)
                tags[tag.api_id] = tag

            student = students.get(tagging.user.id)
            if not student:
                student, _ = Student.objects.get_or_create(tagging.user)
                students[student.api_id] = student

            taggings.setdefault(student, []).append(tag)
            student.tags.add(tag)

        # Update student tags
        for student, active_tags in taggings.items():
            student.tags.set(active_tags)

        # Clear orphaned tags
        active_tag_ids = [tag.id for tag in tags.values()]
        deleted = list(cls.objects.filter(course=course).exclude(id__in=active_tag_ids).all())
        deleted.sort(key=lambda t: t.slug)
        for old_tag in deleted:
            old_tag.delete()

        updated_tags = [tag for tag in tags.values() if tag not in new_tags]
        updated_tags.sort(key=lambda t: t.slug)
        return {
            'new': list(sorted(new_tags, key=lambda t: t.slug)),
            'updated': updated_tags,
            'deleted': deleted,
        }

    def __str__(self):
        return self.name


class Course(NamespacedApiObject):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    instance_name = models.CharField(max_length=255)
    html_url = models.CharField(max_length=255)
    language = models.CharField(max_length=255)

    staff = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                   related_name="courses")

    def __str__(self):
        return "{} - {}".format(self.code, self.name)


class ExerciseManager(NestedApiObject.Manager):
    def with_course(self):
        return self.get_queryset().select_related('course')


class Exercise(NestedApiObject):
    NAMESPACE_FILTER = 'course__namespace'

    objects = ExerciseManager()

    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    html_url = models.CharField(max_length=255)
    course = models.ForeignKey(Course,
                               related_name='exercises',
                               on_delete=models.PROTECT)

    IS_HIERARCHICAL_NAME = re.compile(r"^(?P<round>\d+)\.(?P<chapter>\d+)(\.\d+)* ")

    @property
    def namespace(self):
        return self.course.namespace

    def get_forms(self, path_key=None):
        filters = dict(feedbacks__exercise=self)
        if path_key:
            filters['feedbacks__path_key__startswith'] = path_key
        return FeedbackForm.objects.all().filter(**filters)

    @property
    def unresponded_feedback(self):
        return Feedback.objects.get_notresponded(exercise_id=self.id)

    def __str__(self):
        return self.display_name

    def get_module_and_chapter_numbers_or_keys(self):
        m = self.IS_HIERARCHICAL_NAME.match(self.display_name)
        # The exercise name does not always contain the hierarchical name
        # that shows the round number: "1.2.3 exercise title"
        if m:
            module_key = m.group('round') # e.g. "2"
            chapter_key = m.group('chapter') # e.g. "3"
        else:
            # Assume html_url format: http://plus.domain/coursekey/instancekey/modulekey/chapterkey/exercisekey
            # Only the number of slashes matters for extracting the module key (module = exercise round).
            url_parts = self.html_url.split('/')
            module_key = url_parts[5]
            chapter_key = url_parts[6]
        return module_key, chapter_key


class FeedbackQuerySet(models.QuerySet):

    NEWEST_FLAG = Enum(
        ('', None, _("Newest versions?")),
        ('NEWEST', 'n', _("Newest versions")),
    )
    READ_FLAG = Enum(
        ('', None, _("Read?")),
        ('READ', 'r', _("Read")),
        ('UNREAD', 'u', _("Unread")),
    )
    GRADED_FLAG = Enum(
        ('', None, _("Graded?")),
        ('GRADED', 'g', _("Graded")),
        ('UNGRADED', 'q', _("Ungraded")),
    )
    MANUALLY_FLAG = Enum(
        ('', None, _("Graded how?")),
        ('MANUAL', 'm', _("Manually graded")),
        ('AUTO', 'a', _("Automatically graded")),
    )
    RESPONDED_FLAG = Enum(
        ('', None, _("Responded?")),
        ('RESPONDED', 'h', _("Responded")),
        ('UNRESPONDED', 'i', _("Unresponded")),
    )
    UPLOAD_FLAG = Enum(
        ('', None, _("Upload has error?")),
        ('UPL_ERROR', 'e', _("Upload has error")),
        ('UPL_OK', 'o', _("Upload ok")),
    )

    FLAG_GROUPS = [
        NEWEST_FLAG,
        READ_FLAG,
        GRADED_FLAG,
        MANUALLY_FLAG,
        RESPONDED_FLAG,
        UPLOAD_FLAG,
    ]

    FILTERS = {
        NEWEST_FLAG.NEWEST: Q(superseded_by=None),
        READ_FLAG.UNREAD: Q(response_time=None) & Q(tags=None),
        READ_FLAG.READ: ~(Q(response_time=None) & Q(tags=None)),
        GRADED_FLAG.UNGRADED: Q(response_time=None),
        GRADED_FLAG.GRADED: ~Q(response_time=None),
        RESPONDED_FLAG.UNRESPONDED: Q(response_msg='') | Q(response_msg=None),
        RESPONDED_FLAG.RESPONDED: ~Q(response_time=None) & ~Q(response_msg='') & ~Q(response_msg=None),
        MANUALLY_FLAG.AUTO: ~Q(response_time=None) & Q(response_by=None),
        MANUALLY_FLAG.MANUAL: ~Q(response_time=None) & ~Q(response_by=None),
        UPLOAD_FLAG.UPL_OK: Q(_response_upl_code=200),
        UPLOAD_FLAG.UPL_ERROR: ~Q(_response_upl_code=200) & ~Q(_response_upl_code=0),
    }

    def filter_flags(self, *flags):
        if not flags:
            return self
        try:
            filters = [self.FILTERS[f] for f in flags]
        except KeyError as e:
            raise AttributeError("Invalid flag: {}".format(e))
        q = reduce(Q.__and__, filters)
        return self.filter(q)

    def filter_data(self, search):
        if '*' in search:
            search = search.replace('*', '%')
        else:
            search = ''.join(('%', '%'.join(shlex.split(search)), '%'))
        # TODO: enable AND/OR and friends + make more efficient?
        return self.extra(
            where=['form_data::text ilike %s'],
            params=[search],
        )

    def filter_missed_upload(self, time_gap_min=15):
        gap = timezone.now() - datetime.timedelta(minutes=time_gap_min)
        return self.filter(
            Q(_response_upl_code=0) &
            ~Q(response_time=None) &
            Q(response_time__lt=gap)
        ).order_by('_response_upl_at')

    def filter_failed_upload(self, max_tries=10, time_gap_min=15):
        gap = timezone.now() - datetime.timedelta(minutes=time_gap_min)
        return self.filter(
            ~Q(_response_upl_code=200) &
            ~Q(_response_upl_code=0) &
            Q(_response_upl_attempt__lt=max_tries) &
            Q(_response_upl_at__lt=gap)
        ).order_by('_response_upl_at')

    def feedback_exercises_for(self, course, student):
        q = self.values(
                'exercise_id',
                'path_key',
            ).filter(
                student=student,
                exercise__course=course,
            ).annotate(
                count=models.Count('form_data'),
            ).order_by(
                'exercise__course', 'exercise_id'
            )
        return q

    def get_notresponded(self, exercise_id=None, course_id=None, path_filter=None):
        qs = self.select_related('form', 'exercise').filter_flags(
            self.NEWEST_FLAG.NEWEST,
            self.READ_FLAG.UNREAD,
        )
        if exercise_id is not None:
            qs = qs.filter(exercise__id=exercise_id)
        elif course_id is not None:
            qs = qs.filter(exercise__course__id=course_id)
            if path_filter:
                qs = qs.filter(path_key__startswith=path_filter)
        else:
            raise ValueError("exercise_id or course_id is required")
        return qs.order_by('timestamp')


ResponseUploaded = namedtuple('ResponseUploaded',
                              ('ok', 'when', 'code', 'attempts'))


class Feedback(models.Model):
    objects = FeedbackQuerySet.as_manager()

    class Meta:
        unique_together = [
            ('exercise', 'submission_id'),
        ]

    GRADES = Enum(
        ('NONE', -1, _('No response')), # can't be stored in db (positive integers only)
        ('REJECTED', 0, _('Rejected')),
        ('ACCEPTED', 1, _('Accepted')),
        ('ACCEPTED_GOOD', 2, _('Good')),
    )
    GRADE_CHOICES = [x for x in GRADES.choices if x[0] >= 0]
    MAX_GRADE = GRADES.ACCEPTED_GOOD
    OK_GRADES = (GRADES.ACCEPTED, GRADES.ACCEPTED_GOOD)

    NOTIFY = Enum(
        ('NO', 0, _('No notification')),
        ('NORMAL', 1, _('Normal notification')),
        ('IMPORTANT', 2, _('Important notification')),
    )
    NOTIFY_APLUS = {
        NOTIFY.NORMAL: 'normal',
        NOTIFY.IMPORTANT: 'important',
    }

    # identifier
    exercise = models.ForeignKey(Exercise,
                                 related_name='feedbacks',
                                 on_delete=models.PROTECT,
                                 verbose_name=_("Exercise"))
    submission_id = models.IntegerField()
    path_key = models.CharField(max_length=255, db_index=True)
    max_grade = models.PositiveSmallIntegerField(default=MAX_GRADE)

    # feedback
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    language = models.CharField(max_length=255, default=get_language, null=True)
    student = models.ForeignKey(Student,
                                related_name='feedbacks',
                                on_delete=models.CASCADE,
                                verbose_name=_("Student"))
    form = models.ForeignKey(FeedbackForm,
                             related_name='feedbacks',
                             on_delete=models.PROTECT,
                             null=True)
    form_data = models.JSONField(blank=True)
    superseded_by = models.ForeignKey('self',
                                      related_name="supersedes",
                                      on_delete=models.SET_NULL,
                                      null=True)
    post_url = models.URLField()
    submission_url = models.URLField()
    submission_html_url = models.URLField()

    # response
    response_time = models.DateTimeField(null=True,
                                         verbose_name=_("Response time"))
    response_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    related_name='responded_feedbacks',
                                    on_delete=models.SET_NULL,
                                    null=True,
                                    verbose_name=_("Responder"))
    response_msg = models.TextField(blank=True,
                                    null=True,
                                    default=None,
                                    verbose_name=_("Response message"))
    response_grade = models.PositiveSmallIntegerField(default=GRADES.REJECTED,
                                                      choices=GRADE_CHOICES,
                                                      verbose_name=_("Response grade"))
    response_notify = models.PositiveSmallIntegerField(default=NOTIFY.NO,
                                                       choices=NOTIFY.choices,
                                                       verbose_name=_("Response notify"))

    # response upload
    _response_upl_code = models.PositiveSmallIntegerField(default=0,
                                                          db_column='response_upload_code')
    _response_upl_attempt = models.PositiveSmallIntegerField(default=0,
                                                             db_column='response_upload_attempt')
    _response_upl_at = models.DateTimeField(null=True,
                                            db_column='response_upload_at')


    # Extra getters and properties

    @cached_property
    def course(self):
        return self.exercise.course

    @staticmethod
    def get_exercise_path(exercise, path_key):
        return "{}{}{}".format(
            exercise,
            "/" if path_key else "",
            path_key or '',
        )

    @cached_property
    def exercise_path(self):
        return self.get_exercise_path(self.exercise, self.path_key)

    @property
    def form_class(self):
        return self.form.form_class

    def get_form_class(self, dummy=True):
        return self.form.form_class_or_dummy if dummy else self.form.form_class

    @property
    def form_obj(self):
        return self.form_class(data=self.form_data)

    def get_form_obj(self, dummy=False):
        return self.get_form_class(dummy)(data=self.form_data)

    @property
    def text_feedback(self):
        form = self.get_form_obj(True)
        if form.is_dummy_form:
            return list(self.form_data.items())
        else:
            data = self.form_data
            return [(k, data[k]) for k in form.all_text_fields.keys()]

    @property
    def response_uploaded(self):
        when = self._response_upl_at
        code = self._response_upl_code
        attempts = self._response_upl_attempt
        ok = code in (200,)
        return ResponseUploaded(ok, when, code, attempts)

    @response_uploaded.setter
    def response_uploaded(self, status_code):
        if status_code:
            self._response_upl_code = status_code
            self._response_upl_attempt += 1
            self._response_upl_at = timezone.now()
        else:
            self._response_upl_code = 0
            self._response_upl_attempt = 0
            self._response_upl_at = None
        self.__changed_fields.update(('_response_upl_code', '_response_upl_attempt', '_response_upl_at'))

    @property
    def responded(self):
        return self.response_time is not None

    @property
    def waiting_for_response(self):
        return not self.responded and not self.superseded_by_id

    @property
    def waiting_for_response_msg(self):
        return not self.response_msg and not self.superseded_by_id

    @property
    def can_be_responded(self):
        return bool(self.submission_url)

    @property
    def response_grade_text(self):
        if not self.responded:
            return self.GRADES[self.GRADES.NONE]
        return self.GRADES[self.response_grade]

    @property
    def valid_response_grade(self):
        if not self.responded:
            return None
        return self.response_grade

    @property
    def response_notify_aplus(self):
        return self.NOTIFY_APLUS.get(self.response_notify, '')

    @property
    def older_versions(self):
        return self.__class__.objects.filter(
            ~models.Q(pk=self.pk),
            exercise_id = self.exercise_id,
            student_id = self.student_id,
            timestamp__lt = self.timestamp,
        ).order_by('-timestamp')

    @cached_property
    def older_versions_with_message(self):
        return list(self.older_versions.filter(~models.Q(response_msg='') & ~models.Q(response_msg=None)))

    def __getitem__(self, key):
        return self.feedback[key]

    def __setitem__(self, key, value):
        self.feedback[key] = value


    # Feedback management interface

    @classmethod
    @transaction.atomic
    def create_new_version(cls, **kwargs):
        """
        Creates new feedback object and marks it as parent for all
        old feedbacks by same user to defined resource
        """
        kwargs = {k: v for k,v in kwargs.items() if v is not None}
        new = cls.objects.create(**kwargs)
        assert new.pk is not None, "New feedback doesn't have primary key"
        new.supersede_older()
        return new

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__changed_fields = set()

    def __str__(self):
        return 'Feedback by {} to {} at {}'.format(
            self.student, self.exercise_path, self.timestamp
        )

    def save(self, update_fields=None, **kwargs):
        if update_fields is not None and self.__changed_fields:
            update_fields = tuple(set(update_fields) | self.__changed_fields)
        ret = super().save(update_fields=update_fields, **kwargs)
        self.__changed_fields = set()
        return ret

    def supersede_older(self):
        return self.older_versions.filter(
            superseded_by = None,
        ).update(superseded_by=self)


class FeedbackTag(ColorTag):
    course = models.ForeignKey(Course,
                               related_name="tags",
                               on_delete=models.CASCADE)
    feedbacks = models.ManyToManyField(Feedback,
                                       related_name="tags")

    class Meta(ColorTag.Meta):
        unique_together = ('course', 'slug')

    def is_valid_slug(self, slug):
        # FIXME: returns False if this tag is already added
        # this causes slugs to change if tag is edited
        return slug and not type(self).objects.filter(
            course=self.course,
            slug=slug,
        ).exclude(
            pk=self.pk,
        ).exists()
