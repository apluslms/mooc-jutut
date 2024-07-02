import logging
import re
from typing import (
    Any,
    Callable,
    Optional,
    Tuple,
)
from collections import Counter
from functools import partial
from urllib.parse import urlsplit, urljoin, urlencode

from django.forms import Form
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseBadRequest,
    Http404,
    HttpRequest,
)
from django.utils.text import slugify
from django.utils.timezone import now as timezone_now
from django.utils.translation import get_language, gettext_lazy as _
from django.shortcuts import get_object_or_404
from django.views.generic import FormView, ListView, DetailView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse
from django.core.exceptions import SuspiciousOperation
from django.utils.functional import cached_property
from django.utils.text import format_lazy
from django.contrib import messages

from lib.postgres import PgAvg
from lib.mixins import CSRFExemptMixin, ConditionalMixin
from lib.views import ListCreateView
from lib.helpers import is_ajax, pick_localized
from aplus_client.client import AplusTokenClient
from aplus_client.django.views import AplusGraderMixin

from .models import (
    Site,
    Course,
    Exercise,
    Student,
    StudentTag,
    Conversation,
    Feedback,
    FeedbackForm,
    FeedbackTag,
    ContextTag,
)
from .cached import (
    CachedForm,
    CachedSites,
    CachedCourses,
    CachedTags,
    CachedNotrespondedCount,
    MiscCache,
    BackgroundCache,
)
from .forms import (
    ResponseForm,
    FeedbackTagForm,
    ContextTagForm,
    ImportTagsForm,
)
from .forms_dynamic import DynamicFeedbacForm
from .filters import FeedbackFilter
from .permissions import (
    CheckManagementPermissionsMixin,
    AdminOrSiteStaffPermission,
    AdminOrCourseStaffPermission,
    AdminOrFeedbackStaffPermission,
    AdminOrTagStaffPermission,
)
from .utils import (
    get_url_reverse_resolver,
    obj_with_attrs,
)


logger = logging.getLogger('jutut.feedback')



# Feedback a-plus interface
# -------------------------


class SuspiciousStudent(SuspiciousOperation):
    pass


class FeedbackAverageView(ListView):
    """Example of postgresql json aggregation. Remove when used in analysis"""
    # NOTE: not linked in urls.py. exists to remind how annotates work
    model = Feedback
    template_name = 'feedback/avglist.html'

    def get_queryset(self):
        return Feedback.objects.all(
        ).values(
            'course_id',
            'exercise_id',
            'path',
        ).filter(
            superseded_by=None,
            form_data__has_key='timespent',
        ).annotate(
            avg=PgAvg('form_data', 'timespent')
        )


class FeedbackSubmissionView(CSRFExemptMixin, AplusGraderMixin, FormView):
    """
    This is view implements A-Plus interfaces to get feedback submissions
    """
    template_name = 'feedback/new.html'
    success_url = '/feedback/'
    form_class = None
    form_cache_key = None

    def get_form_class(self):
        if self.form_class:
            return self.form_class

        self.path_key = path_key = self.kwargs.get('path_key', '').strip('/')
        form_obj = None

        # get latest form object or create new
        post_url = urlsplit(self.post_url)
        if post_url.path and path_key:
            self.form_cache_key = cache_key = ''.join((post_url.netloc, post_url.path, path_key))
            try:
                form_obj = CachedForm.get(
                    cache_key,
                    lambda: self.grading_data.form_spec,
                    lambda: self.grading_data.form_i18n,
                )
            except ValueError as e:
                logger.warning(
                    "failed to create form_spec: %s: %s; api: %s",
                    e.__class__.__name__, e, self.grading_data.exercise_api,
                )

        # if we can't use cache, use the "old way"
        else:
            form_spec = self.grading_data.form_spec
            form_i18n = self.grading_data.form_i18n
            if form_spec:
                try:
                    form_obj = FeedbackForm.objects.get_or_create(form_spec=form_spec, form_i18n=form_i18n)
                except ValueError as e:
                    logger.warning(
                        "failed to create form_spec: %s: %s; api: %s",
                        e.__class__.__name__, e, self.grading_data.exercise_api,
                    )

        if form_obj:
            self.form_obj = form_obj
            auto_id = "jutut_{}_%s".format(slugify(post_url.path or path_key))
            try:
                self.form_class = form_class = partial(form_obj.form_class, auto_id=auto_id)
            except AttributeError as e:
                logger.error(
                    "form_spec contained invalid data: %s: %s; api: %s",
                    e.__class__.__name__, e, self.grading_data.exercise_api,
                )
                raise Http404("form_spec contained invalid data") from e
            return form_class

        logger.critical("form_spec not resolved from submission_url '%s'", self.submission_url)
        raise Http404("form_spec not found from provided submission_url")

    def reload_form_class(self):
        cache_key = self.form_cache_key
        if cache_key:
            form_obj_id = getattr(self.form_obj, 'id', None)
            CachedForm.clear(cache_key)
            self.form_class = None
            self.get_form_class()
            return form_obj_id != self.form_obj.id
        return False

    def get_student(self, namespace):
        student = None

        # Try to resolve student using uid from query parameters
        uids = self.request.GET.get('uid', '').split('-')
        if len(uids) > 1:
            raise SuspiciousStudent("Multiple uids in query uid field")
        if len(uids) == 1 and uids[0]:
            try:
                student = Student.objects.using_namespace(namespace).get(api_id=uids[0])
            except (Student.DoesNotExist, ValueError):
                pass

        # Fallback to resolve student from grading_data
        if not student:
            students = self.grading_data.submitters
            if not students:
                raise SuspiciousStudent("Failed to resolve students")
            if len(students) != 1:
                raise SuspiciousStudent("Multiple students in submission. Feedback expects only one")
            student, _created = Student.objects.get_new_or_updated(students[0], namespace=namespace)

        return student

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['post_url'] = self.post_url
        context['jutut_path'] = self.path_key
        context['aplus_path'] = self.submission_url
        return context

    def form_valid(self, form): # pylint: disable=too-many-locals
        gd = self.grading_data
        path_key = self.path_key
        exercise_obj = gd.exercise
        # Fetch the Jutut exercise based on the API ID (exercise ID in the A+ database).
        # If it does not exist yet, the exercise is created in the Jutut database.
        # When the exercise is created, the other fields are filled in with
        # the data from exercise_obj.
        exercise, _created = Exercise.objects.get_or_create(
            exercise_obj,
            select_related=('course', 'course__namespace'),
        ) if exercise_obj else (None, False)
        if not exercise:
            logger.warning("exercise not resolved from submission_url '%s'", self.submission_url)
            return HttpResponseBadRequest("exercise not found from provided submission_url")
        # Change the display name to the hierarchical name that always contains
        # the module and chapter numbers.
        hierarchical_name = exercise_obj._data.get('hierarchical_name')
        if hierarchical_name and hierarchical_name != exercise.display_name:
            exercise.display_name = hierarchical_name
            exercise.save()
        try:
            student = self.get_student(exercise.namespace)
        except SuspiciousStudent as err:
            logger.warning("failed to resolve student: %s", err)
            return HttpResponseBadRequest(str(err))

        max_grade = self.max_points
        if max_grade is None:
            max_grade = Feedback.MAX_GRADE
        else:
            max_grade = min(max_grade, Feedback.MAX_GRADE)

        # Common data for feedback
        data = {
            'student': student,
            'form': self.form_obj,
            'form_data': form.cleaned_data,
            'max_grade': max_grade,
            'post_url': self.post_url or '',
            'submission_url': self.submission_url or '',
            'submission_html_url': gd.html_url,
            'timestamp': gd.submission_time,
            'response_seen': gd.feedback_response_seen
        }

        # find if there is submission we should update (aplus resend action for example)
        try:
            feedback = Feedback.objects.get(exercise=exercise, submission_id=gd.submission_id)
            feedback.exercise = exercise
        except Feedback.DoesNotExist:
            feedback = None

        # update
        if feedback:
            for k, v in data.items():
                if v is not None:
                    setattr(feedback, k, v)
            feedback.save()

        # create
        else:
            # automatically grade if there is no need for human oversight
            if not form.requires_manual_check:
                data['response_grade'] = max_grade
                data['response_time'] = timezone_now()

            # will create and save new feedback
            # will also take care of marking old feedbacks
            feedback = Feedback.create_new_version(
                exercise = exercise,
                submission_id = gd.submission_id,
                path_key = path_key,
                **data,
            )

        status = 'graded' if feedback.responded or not form.is_graded else 'accepted'
        points = feedback.response_grade if form.is_graded else feedback.max_grade
        return self.render_to_response(self.get_context_data(status=status, points=points, feedback=feedback))

    def form_invalid(self, form):
        if self.reload_form_class():
            form = self.get_form()
            if form.is_valid():
                return self.form_valid(form)
        return super().form_invalid(form)



# Feedback management (admin)
# ---------------------------

class ManageSiteMixin(CheckManagementPermissionsMixin):
    permission_classes = [AdminOrSiteStaffPermission]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_superuser or user.is_staff:
            context['sitelist'] = CachedSites.get
        else:
            visible_sites = self.visible_sites
            # pylint: disable-next=no-value-for-parameter
            context['sitelist'] = [site for site in CachedSites.get() if site.id in visible_sites]
        site = context.get('site', None)
        if site:
            context['sitename'] = '.'.join(site.domain.split('.', 2)[:2])
            if user.is_superuser or user.is_staff:
                courselist = CachedCourses.get(site)
            else:
                visible_courses = self.visible_courses
                courselist = [c for c in CachedCourses.get(site) if c.id in visible_courses]
            # create names for course list entries. Different instances contain instance_name
            dup_courses = frozenset(code for code, count in Counter(c.code for c in courselist).items() if count > 1)
            fmt1 = "{c.code} - {c.name}"
            fmt2 = "{c.code} - {c.name} ({c.instance_name})"
            courselist = [
                (c, (fmt2 if c.code in dup_courses else fmt1).format(c=c))
                for c in courselist
            ]
            context['courselist'] = courselist
            # use instance name in course name if duplicate is in list
            course = kwargs.get('course', None)
            if course and course.code in dup_courses:
                context['course_name'] = fmt2.format(c=course)
        return context


class ManageCourseMixin(ManageSiteMixin):
    permission_classes = [AdminOrCourseStaffPermission]

    @cached_property
    def course(self):
        return get_object_or_404(Course, pk=self.kwargs['course_id'])

    def get_context_data(self, **kwargs):
        course = kwargs.get('course')
        if not course:
            kwargs['course'] = course = self.course
        kwargs.setdefault('site', course.namespace)
        context = super().get_context_data(**kwargs)
        context['course_notresponded'] = CachedNotrespondedCount.get(course)
        context.setdefault('course_name', str(course))
        return context


class ManageSiteListView(ManageSiteMixin, ListView):
    model = Site
    template_name = "manage/site_list.html"
    context_object_name = "sites"

    def get_queryset(self):
        qs = self.model.objects.all()
        user = self.request.user
        if not user.is_superuser and not user.is_staff:
            qs = qs.filter(id__in=self.visible_sites)
        return qs


class ManageCourseListView(ManageSiteMixin, ListView):
    model = Course
    template_name = "manage/course_list.html"
    context_object_name = "courses"

    def get_queryset(self):
        site_id = self.kwargs.get('site_id', None)
        if site_id is not None:
            self._site = site = get_object_or_404(Site, pk=site_id)
            qs = self.model.objects.using_namespace(site)
        else:
            self._site = None
            qs = self.model.objects
        user = self.request.user
        if not user.is_superuser and not user.is_staff:
            qs = qs.filter(id__in=self.visible_courses)
        return qs.all().order_by('namespace', 'api_id')

    def get_context_data(self, **kwargs):
        return super().get_context_data(site=self._site, **kwargs)


class ManageUpdateStudenttagsView(ManageCourseMixin, TemplateView):
    template_name = "manage/update_studenttags.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.course
        last_updated = course.student_tags_updated
        if last_updated:
            context['prev_update_time'] = last_updated
        return context

    def get(self, request, *args, **kwargs):
        kwargs['has_token'] = request.user.has_api_token(self.course.namespace)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        course = self.course
        client = request.user.get_api_client(course.namespace)
        tags = None
        if client:
            tags = StudentTag.update_from_api(client, course)
        kwargs['has_token'] = bool(client)
        kwargs['tags'] = tags
        return super().get(request, *args, **kwargs)


def get_tag_list(tags, conversation, get_tag_url=None) -> Tuple[FeedbackTag]:
    active = conversation.tags.all()
    return (
        obj_with_attrs(tag,
                       is_active=(tag in active),
                       data_attrs=({'url': get_tag_url(conversation, tag)} if get_tag_url else None))
        for tag in tags
    )


def get_feedback_dict(feedback, get_form, response_form_class, # pylint: disable=too-many-arguments
                      get_post_url=None, get_status_url=None,
                      active=True) -> dict:
    form = get_form(feedback)
    data = {
        'form': response_form_class(instance=feedback),
        'feedback': feedback,
        'feedback_form': form,
        'feedback_form_grading': feedback.max_grade > 1 and (form.is_dummy_form or form.is_graded),
        'active': active,
    }
    if get_post_url:
        data['post_url'] = get_post_url(feedback)
    if get_status_url:
        data['status_url'] = get_status_url(feedback)
    return data


def update_context_for_feedbacks( # noqa
        request: HttpRequest,
        context: dict[str, Any],
        course: Optional[Course] = None,
        feedbacks: Optional[list[Feedback]] = None,
        get_form: Optional[Callable[[Feedback], DynamicFeedbacForm]] = None,
        post_url: bool = True,
        ) -> None:
    # defaults for parameters
    if not course:
        course = context['course']
    if not feedbacks:
        feedbacks = context['object_list']
    if not get_form:
        get_form = lambda o: o.get_form_obj(dummy=True) # pylint: disable=unnecessary-lambda-assignment
    course_id = course.id

    # get_post_url
    get_post_url = get_url_reverse_resolver(
        'feedback:respond',
        ('feedback_id',),
        lambda f: (f.id,),
        query={"success_url": request.get_full_path()},
    ) if post_url else None

    # get_status_url
    get_status_url = get_url_reverse_resolver(
        'feedback:status',
        ('feedback_id',),
        lambda f: (f.id,),
    )

    # all_student_feedbacks_for_exercise_url
    get_all_student_feedbacks_for_exercise_url = get_url_reverse_resolver(
        'feedback:list',
        ('course_id',),
        lambda f: (course_id,),
        query_func=lambda f: {
            'student': f.student.id,
            'exercise': f.exercise.id,
        },
    )

    # all_feedbacks_url
    get_all_feedbacks_url = get_url_reverse_resolver(
        'feedback:list',
        ('course_id',),
        lambda o: (course_id,),
        query_func=lambda f: {'student': f.student.id,},
    )

    # all_feedbacks_for_exercise_url
    get_all_feedbacks_for_exercise_url = get_url_reverse_resolver(
        'feedback:list',
        ('course_id',),
        lambda o: (course_id,),
        query_func=lambda f: {'exercise': f.exercise.id,},
    )

    # get_tag_url
    tags = CachedTags.get(course)
    get_tag_url = get_url_reverse_resolver('feedback:tag',
                                           ('conversation_id', 'tag_id'),
                                           lambda c, t: (c.id, t.id))

    course_context_tags = ContextTag.objects.filter(course=course_id)
    context_tag_groups: dict[str, dict[str, ContextTag]] = {} # {question_key: {response_value: ContextTag}}
    for tag in course_context_tags:
        tag_group = context_tag_groups.setdefault(tag.question_key, {})
        tag_group[tag.response_value] = tag

    # get background questionnaire urls
    client = request.user.get_api_client(course.namespace)
    if client:
        course_has_bg_questionnaire = (
            # pylint: disable-next=no-value-for-parameter
            len(BackgroundCache.get_or_set_bg_questionnaires(course, client)) > 0
        )
    else:
        bg_q_dict = BackgroundCache.get_bg_questionnaires(course) # pylint: disable=no-value-for-parameter
        course_has_bg_questionnaire = bool(bg_q_dict) and len(bg_q_dict) > 0
        context['errors_title'] = _("Missing A+ API token!")
        context['errors'] = _(
            "Some features will not fully work due to the missing A+ API token. " +
            "Log in via A+ and access this site through the course menu."
        )

    def student_may_have_bg_questionnaire(student: Student) -> bool:
        # check if student has bg response or it hasn't been fetched yet
        resp = BackgroundCache.get_response(student, course) # pylint: disable=no-value-for-parameter
        return (resp is None) or (resp[0] is not None)

    # group feedbacks by conversation
    convs: dict[Conversation, list[Feedback]] = {}
    for f in feedbacks:
        if f.conversation in convs:
            convs[f.conversation].append(f)
        else:
            convs[f.conversation] = [f]

    def get_conversation_dict(conv: Conversation, fbs: list[Feedback]) -> dict:
        conv_feedback = [
            get_feedback_dict(
                f,
                get_form=get_form,
                response_form_class=ResponseForm,
                get_post_url=get_post_url,
                get_status_url=get_status_url,
                active=(f in fbs)
            ) for f in conv.feedbacks.all().order_by('timestamp')
        ]
        # check whether feedback should have context tags, and if so, render them
        context_tags = []
        last_fb_dict = conv_feedback[-1]
        for key, field in last_fb_dict['feedback_form'].fields.items(): # pylint: disable=too-many-nested-blocks
            if key in context_tag_groups:
                r_value = str(last_fb_dict['feedback'].form_data[key])
                for r_k in context_tag_groups[key].keys():
                    try:
                        if re.fullmatch(r_k, r_value):
                            c_tag = context_tag_groups[key][r_k]
                            tooltip_text = field.help_text
                            if hasattr(field, 'choices'):
                                map_ = dict(field.choices)
                                display_value = map_[r_value]
                            else:
                                display_value = r_value
                            tooltip_text += " -- " + display_value
                            context_tags.append(c_tag.render_tag(tooltip_text, r_value))
                    except re.error:
                        pass

        conv_dict = {
            'id': conv.id,
            'student': conv.student,
            'exercise': conv.exercise,
            'all_feedback_for_student_url': get_all_feedbacks_url(conv),
            'student_aplus_url': course.html_url + f'teachers/participants/{conv.student.api_id}',
            'all_feedback_for_exercise_url' : get_all_feedbacks_for_exercise_url(conv),
            'student_feedback_for_exercise_url': (
                request.build_absolute_uri(get_all_student_feedbacks_for_exercise_url(conv))
            ),
            'show_background': course_has_bg_questionnaire and student_may_have_bg_questionnaire(conv.student),
            'context_tags': context_tags,
            'conversation_tags': set(conv.tags.all()),
            'feedback_list': conv_feedback,
        }
        if tags:
            conv_dict['tags'] = get_tag_list(tags, conv, get_tag_url)
        return conv_dict

    context['conversations'] = [get_conversation_dict(c, fbs) for c, fbs in convs.items()]


class PaginatedMixin():
    paginate_by = 50
    PAGE_SIZE_CHOICES = ("20", "50", "100", "200")

    def get_paginate_by(self, queryset): # pylint: disable=unused-argument
        value = self.request.GET.get('paginate_by')
        if value is not None and value in self.PAGE_SIZE_CHOICES:
            self.paginate_by = int(value)
        return self.paginate_by

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context['page_sizes'] = list(map(
            lambda size: (size, int(size) == self.paginate_by),
            self.PAGE_SIZE_CHOICES))
        feedbacks = context['paginator'].object_list
        context['total_conversation_count'] = len({f.conversation.id for f in feedbacks})
        return context


class ManageNotRespondedListView(ManageCourseMixin, PaginatedMixin, ListView):
    model = Feedback
    template_name = "manage/feedback_unread.html"

    def get_queryset(self):
        course_id = self.kwargs['course_id']
        self.course = get_object_or_404(Course, pk=course_id)
        self._path_filter = path_filter = self.kwargs.get('path_filter', '').strip('/')
        return Feedback.objects.get_notresponded(course_id=course_id, path_filter=path_filter)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(course=self.course, **kwargs)
        context['path_filter'] = self._path_filter
        update_context_for_feedbacks(self.request, context)
        return context


class ManageFeedbacksListView(ManageCourseMixin, PaginatedMixin, ListView):
    model = Feedback
    template_name = "manage/feedback_list.html"

    def get_queryset(self):
        course = self.course
        queryset = Feedback.objects.filter(exercise__course=course)
        # pylint: disable-next=redefined-builtin
        self.feedback_filter = filter = FeedbackFilter(self.request.GET, queryset, course=course)
        return filter.qs

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(course=self.course, **kwargs)
        context['feedback_filter'] = self.feedback_filter
        update_context_for_feedbacks(self.request, context)
        return context


class UserListView(ManageCourseMixin, ListView):
    model = Student
    template_name = "manage/user_list.html"
    context_object_name = "students"

    def get_queryset(self):
        return self.model.objects.get_students_on_course(self.course)


class UserFeedbackListView(ManageCourseMixin, ListView):
    model = Feedback
    template_name = "manage/user_feedback_list.html"
    context_object_name = "feedbacks"

    def get_queryset(self):
        course = self.course
        self.student = student = get_object_or_404(Student, pk=self.kwargs['user_id'])
        return self.model.objects.feedback_exercises_for(course, student)

    def get_context_data(self, **kwargs):
        course = self.course
        context = super().get_context_data(**kwargs)
        feedbacks = list(context['feedbacks'])
        exercises = list(set(f['exercise_id'] for f in feedbacks))
        exercises = Exercise.objects.filter(pk__in=exercises)
        exercises = {e.id: e for e in exercises}
        all_student_feedbacks_for_exercise_url = get_url_reverse_resolver(
            'feedback:list',
            ('course_id',),
            lambda o: (course.id,),
            query_func=lambda f: {'student': self.student.id, 'exercise': f['exercise_id']},
        )

        def get_feedback(f):
            f['exercise'] = exercise = exercises[f['exercise_id']]
            f['exercise_path'] = Feedback.get_exercise_path(exercise, f['path_key'])
            f['url_to_filter'] = all_student_feedbacks_for_exercise_url(f)
            return f
        context['feedbacks'] = (get_feedback(feedback) for feedback in feedbacks)
        context['student'] = self.student
        return context


class StudentBackgroundView(CheckManagementPermissionsMixin, TemplateView):
    permission_classes = [AdminOrCourseStaffPermission]
    template_name = "manage/_background.html"

    @cached_property
    def background_objects(self) -> tuple[Course, Student]:
        kwargs = self.kwargs
        course_id = kwargs.get('course_id')
        student_id = kwargs.get('student_id')
        course = get_object_or_404(Course, id=course_id)
        student = get_object_or_404(Student, id=student_id)
        return (course, student)

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        course, student = self.background_objects
        client = self.request.user.get_api_client(course.namespace)

        if client:
            bgq_id, response = BackgroundCache.get_or_set_response( # pylint: disable=no-value-for-parameter
                student, course, client
            )
        else:
            res = BackgroundCache.get_response( # pylint: disable=no-value-for-parameter
                student, course,
            )
            if res:
                bgq_id, response = res
            else:
                context['errors'] = _(
                    "Unable to fetch content due to missing A+ API token. " +
                    "Log in via A+ and access this site through the course menu."
                )
                return context
        if not bgq_id: # student hasn't responded to background questionnaire
            return context
        # pylint: disable-next=no-value-for-parameter
        bg_questionnaire = BackgroundCache.get_bg_questionnaires(course)[bgq_id]
        lang = get_language()

        # calculate question info and response values in correct language
        res = []
        for key, value in response.items():
            # general question info in correct language
            r_dict = {
                k: v[lang] if isinstance(v, dict) else v
                for k, v in bg_questionnaire['questions'][key].items() if k != 'answer_opts'
            }
            q_dict = bg_questionnaire['questions'][key]
            if q_dict['type'] in 'textarea': # text or textarea
                r_dict['response'] = value
            elif q_dict['type'] in ['radio', 'dropdown']:
                r_dict['response'] = q_dict['answer_opts'][value][lang]
            elif q_dict['type'] == 'checkbox': # value is list of responses
                r_dict['response'] = [q_dict['answer_opts'][v][lang] for v in value]
            # add response info to results
            res.append(r_dict)
        context['questions'] = res
        context['title'] = pick_localized(bg_questionnaire['display_name'], lang)
        return context


def get_exercises_per_feedback_dict(course: Course, client: AplusTokenClient):
    tree_api = client.load_data(f"{course.url}/tree")
    # get feedback exercises from Jutut DB to identify which exercises in API are feedback
    fb_exercises = list(course.exercises.values_list('api_id', flat=True))
    exercise_dict = {}
    for mod in tree_api.get("modules"):
        for chap in mod.get("children"):
            ex_ids = [e.get("id") for e in chap.get("children")]
            for e_id in ex_ids:
                # create entry for each Jutut feedback to relatives
                if e_id in fb_exercises:
                    exercise_dict[e_id] = {
                        'exercise_ids': ex_ids,
                        'chapter_name': chap.get("name"),
                        'module_name': mod.get("name"),
                        'module_id': mod.get("id"),
                    }
    return exercise_dict


class FeedbackPointsView(CheckManagementPermissionsMixin,
                         DetailView):
    model = Conversation
    context_object_name = 'conversation'
    pk_url_kwarg = 'conversation_id'
    permission_classes = [AdminOrFeedbackStaffPermission]
    template_name = "manage/_points.html"

    @cached_property
    def object(self): # pylint: disable=method-hidden
        return self.get_object()

    def get_context_data(self, **kwargs): # pylint: disable=too-many-locals
        context = super().get_context_data(**kwargs)
        conv = self.object
        exercise = conv.exercise
        course = exercise.course
        client = self.request.user.get_api_client(course.namespace)
        if not client:
            context['errors'] = _(
                "Unable to fetch content due to missing A+ API token. " +
                "Log in via A+ and access this site through the course menu."
            )
            return context
        lang = get_language()
        # fetch mapping of feedback exercise to all exercises in same chapter,
        fb_exercise_dict = MiscCache.get('fb_exercise_dict', course) # pylint: disable=no-value-for-parameter
        # if hasn't been calculated yet or Jutut didn't know of feedback
        # exercise during previous calculation, (re)calculate and cache
        if (fb_exercise_dict is None) or (exercise.api_id not in fb_exercise_dict):
            fb_exercise_dict = get_exercises_per_feedback_dict(course, client)
            MiscCache.set('fb_exercise_dict', course, fb_exercise_dict, None)
        fb_relatives = fb_exercise_dict.get(exercise.api_id)

        # fetch points for user and calculate points for course, module and chapter
        points_api = client.load_data(f"{course.url}/points/{conv.student.api_id}")
        total_dict = {
            'points': points_api.get('points'),
            'max_points': points_api.get('max_points'),
            'passed': True,
        }
        # points per category for the whole course
        points_by_cat = points_api.get('points_by_difficulty')
        max_points_by_cat = points_api.get('max_points_by_difficulty')
        category_dict = {}
        for k in max_points_by_cat.keys():
            category_dict[k] = {
                'points': points_by_cat.get(k, 0),
                'max_points': max_points_by_cat.get(k),
                'passed': True,
            }
        # module
        module = next(m for m in points_api.get("modules")
                      if m.get("id") == fb_relatives['module_id'])
        module_dict = {
            k: module.get(k)
            for k in ['points', 'max_points', 'passed']
        }
        module_dict['name'] = pick_localized(fb_relatives['module_name'], lang)
        # calculate points for exercises in the same chapter
        chapter_dict = {
            'name': pick_localized(fb_relatives['chapter_name'], lang),
            'points': 0,
            'max_points': 0,
            'passed': True,
        }
        chapter_exs = [e for e in module.get('exercises')
                       if e.get("id") in fb_relatives['exercise_ids']]
        for e in chapter_exs:
            for key in ['points', 'max_points']:
                chapter_dict[key] += e[key]
            if not e.get('passed'):
                chapter_dict['passed'] = False

        # calculate info for progress bars
        for d in [module_dict, chapter_dict, *category_dict.values()]:
            d['percentage'] = d['points'] / d['max_points'] * 100
            d['full_score'] = (d['points'] == d['max_points'])

        context['points'] = {
            'total': total_dict,
            'by_category': category_dict,
            'module': module_dict,
            'chapter': chapter_dict,
        }
        return context


class FeedbackMixin(CheckManagementPermissionsMixin):
    model = Feedback
    context_object_name = 'feedback'
    pk_url_kwarg = 'feedback_id'
    permission_classes = [AdminOrFeedbackStaffPermission]

    @cached_property
    def object(self):
        return self.get_object()

    def get_context_data(self, **kwargs):
        feedback = self.object
        context = super().get_context_data(course=feedback.exercise.course, **kwargs)
        update_context_for_feedbacks(self.request, context, feedbacks=[feedback], post_url=False)
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class SingleFeedbackMixin(FeedbackMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # unpack single feedback out of feedbacks
        conv = context['conversations'][0]
        for f_dict in conv['feedback_list']:
            if f_dict['feedback'].id == context['feedback'].id:
                context.update(f_dict)
                break
        return context


class RespondFeedbackMixin(FeedbackMixin):
    form_class = ResponseForm
    success_url_param = 'success_url'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        success_url = self.request.GET.get(self.success_url_param)
        if success_url:
            context['post_url'] = urljoin(self.request.path,
                                          '?'+urlencode({self.success_url_param: success_url}))
        logger.debug(context)
        return context

    def form_valid(self, form):
        result = super().form_valid(form)
        if isinstance(result, HttpResponseRedirect) and is_ajax(self.request):
            # return form as we would have done with invalid case, but signal client with 201 code that it was created
            logger.debug("Ajax POST ok, returning original form with status 201")
            return self.render_to_response(self.get_context_data(form=form), status=201)
        return result

    def get_success_url(self):
        url = self.request.GET.get(self.success_url_param)
        if not url:
            url = reverse('feedback:notresponded-course', kwargs={
                'course_id': self.object.form.exercise.course.id,
            })
        return url


class RespondFeedbackView(RespondFeedbackMixin,
                          ManageCourseMixin,
                          UpdateView):
    template_name = "manage/response_form.html"


class RespondFeedbackViewAjax(RespondFeedbackMixin,
                              SingleFeedbackMixin,
                              UpdateView):
    template_name = "manage/response_form_ajax.html"

    def get_success_url(self):
        # skip redirect url resolving for ajax request, as it will be replaced
        return None


class ResponseStatusView(ConditionalMixin,
                         SingleFeedbackMixin,
                         DetailView):
    template_name = "manage/_upload_status.html"

    def get_last_modified(self, request):
        return self.object.response_uploaded.when


def respond_feedback_view_select(normal_view, ajax_view):
    def dispatch(request, *args, **kwargs):
        view = ajax_view if is_ajax(request) else normal_view
        return view(request, *args, **kwargs)
    return dispatch


class FeedbackTagMixin(ManageCourseMixin):
    model = FeedbackTag
    form_class = FeedbackTagForm
    pk_url_kwarg = 'tag_id'
    context_object_name = "tag"

    def get_success_url(self):
        return reverse('feedback:tags', kwargs={'course_id': self.course.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['edit_model_text'] = _("Edit feedback tag")
        context['add_model_text'] = _("Add new feedback tag")
        context['urlpattern'] = "feedback:tags"
        return context


class FeedbackTagEditView(FeedbackTagMixin, UpdateView):
    template_name = "feedback_tags/tag_edit.html"


class FeedbackTagDeleteView(FeedbackTagMixin, DeleteView):
    template_name = "feedback_tags/tag_confirm_delete.html"
    # Use an empty form that is always valid, deletion form doesn't need to
    # require all the fields of the FeedbackTag model
    form_class = Form


class FeedbackTagListView(FeedbackTagMixin, ListCreateView):
    template_name = "feedback_tags/tag_list.html"
    context_object_name = "tags"

    def get_queryset(self):
        return self.model.objects.filter(course=self.course)

    def get_form_kwargs(self):
        self.object = self.model(course=self.course)
        return super().get_form_kwargs()


class ImportTagsView(ManageCourseMixin, FormView):
    template_name = "feedback_tags/import_tags.html"
    form_class = ImportTagsForm

    def get_course_options(self):
        """Get all courses that are visible to the current user and are
        not the current course. Used as options where to import tags from.
        """
        return Course.objects.filter(id__in=self.visible_courses).exclude(id=self.course.id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['target_course'] = self.course
        kwargs['course_options'] = self.get_course_options()
        return kwargs

    def get_context_data(self, **kwargs):
        course_options = self.get_course_options()
        existing_tags = set(FeedbackTag.objects.filter(
            course=self.course).values_list('slug', flat=True))
        course_option_ids = course_options.values_list('id', flat=True)
        tags = FeedbackTag.objects.filter(course__id__in=course_option_ids)
        tags_dict = {
            id: [] for id in course_option_ids
        }
        for tag in tags:
            tag.canImport = tag.slug not in existing_tags
            tags_dict[tag.course.id].append(tag)
        for course_id in tags_dict:
            tags_dict[course_id].sort(key=lambda tag: -int(tag.canImport))
        kwargs['course_tags'] = tags_dict.items()
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        imported_tags = form.copy_tags()
        if len(imported_tags) > 0:
            messages.success(
                self.request,
                format_lazy(
                    _('Imported successfully tags: {imported_tags}.'),
                    imported_tags=', '.join(imported_tags)
                )
            )
        else:
            messages.warning(
                self.request,
                _('No tags were imported.')
            )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('feedback:tags-import', kwargs={'course_id': self.course.id})


class FeedbackTagView(CheckManagementPermissionsMixin, View):
    permission_classes = [AdminOrTagStaffPermission]

    @cached_property
    def tag_objects(self) -> Tuple[Conversation, FeedbackTag]:
        kwargs = self.kwargs
        conversation_id = kwargs['conversation_id']
        tag_id = kwargs.get('tag_id')
        conversation = get_object_or_404(Conversation, id=conversation_id)
        tag = get_object_or_404(FeedbackTag, id=tag_id) if tag_id is not None else None
        return (conversation, tag)

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data()
        conversation, _tag = self.tag_objects
        context['conversation'] = conversation
        return context

    def put(self, *args, **kwargs) -> HttpResponse:
        conversation, tag = self.tag_objects
        if conversation.exercise.course != tag.course:
            return HttpResponseBadRequest("Tag and feedback are not part of same course")
        conversation.tags.add(tag)
        return HttpResponse("ok")

    def delete(self, *args, **kwargs) -> HttpResponse:
        conversation, tag = self.tag_objects
        conversation.tags.remove(tag)
        return HttpResponse("ok")


class ContextTagMixin(ManageCourseMixin):
    model = ContextTag
    form_class = ContextTagForm
    pk_url_kwarg = 'tag_id'
    context_object_name = "tag"

    def get_success_url(self):
        return reverse('feedback:contexttags', kwargs={'course_id': self.course.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['edit_model_text'] = _("Edit context tag")
        context['add_model_text'] = _("Add new context tag")
        context['urlpattern'] = "feedback:contexttags"
        return context


class ContextTagEditView(ContextTagMixin, UpdateView):
    template_name = "feedback_tags/tag_edit.html"


class ContextTagDeleteView(ContextTagMixin, DeleteView):
    template_name = "feedback_tags/contexttag_confirm_delete.html"
    # Use an empty form that is always valid, deletion form doesn't need to
    # require all the fields of the FeedbackTag model
    form_class = Form


class ContextTagListView(ContextTagMixin, ListCreateView):
    template_name = "feedback_tags/contexttag_list.html"
    context_object_name = "tags"

    def get_queryset(self):
        return self.model.objects.filter(course=self.course)

    def get_form_kwargs(self):
        self.object = self.model(course=self.course)
        return super().get_form_kwargs()
