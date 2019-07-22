import logging
from collections import Counter
from datetime import timedelta
from functools import partial
from urllib.parse import urlsplit, urljoin, urlencode
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.utils.text import slugify
from django.utils.timezone import now as timezone_now
from django.shortcuts import get_object_or_404
from django.views.generic import FormView, ListView, DetailView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse
from django.core.exceptions import SuspiciousOperation
from django.utils.functional import cached_property

from lib.postgres import PgAvg
from lib.mixins import CSRFExemptMixin, ConditionalMixin
from lib.views import ListCreateView
from aplus_client.django.views import AplusGraderMixin

from django_dictiterators.utils import NestedDictIterator


from .models import (
    Site,
    Course,
    Exercise,
    Student,
    StudentTag,
    Feedback,
    FeedbackForm,
    FeedbackTag,
)
from .cached import (
    FormCache,
    CachedForm,
    CachedSites,
    CachedCourses,
    CachedTags,
    CachedNotrespondedCount,
)
from .forms import (
    ResponseForm,
    FeedbackTagForm,
)
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
                form_obj = CachedForm.get(cache_key, lambda: self.grading_data.form_spec, lambda: self.grading_data.form_i18n)
            except ValueError as e:
                logger.warning("failed to create form_spec: %s: %s; api: %s", e.__class__.__name__, e, self.grading_data.exercise_api)

        # if we can't use cache, use the "old way"
        else:
            form_spec = self.grading_data.form_spec
            form_i18n = self.grading_data.form_i18n
            if form_spec:
                try:
                    form_obj = FeedbackForm.objects.get_or_create(form_spec=form_spec, form_i18n=form_i18n)
                except ValueError as e:
                    logger.warning("failed to create form_spec: %s: %s; api: %s", e.__class__.__name__, e, self.grading_data.exercise_api)

        if form_obj:
            self.form_obj = form_obj
            auto_id = "jutut_{}_%s".format(slugify(post_url.path or path_key))
            try:
                self.form_class = form_class = partial(form_obj.form_class, auto_id=auto_id)
            except AttributeError as e:
                logger.error("form_spec contained invalid data: %s: %s; api: %s", e.__class__.__name__, e, self.grading_data.exercise_api)
                raise Http404("form_spec contained invalid data")
            return form_class
        else:
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
            student = Student.objects.get_new_or_updated(students[0], namespace=namespace)

        return student

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['post_url'] = self.post_url
        context['jutut_path'] = self.path_key
        context['aplus_path'] = self.submission_url
        return context

    def form_valid(self, form):
        gd = self.grading_data
        path_key = self.path_key
        exercise_obj = gd.exercise
        exercise, created = Exercise.objects.get_or_create(exercise_obj, select_related=('course', 'course__namespace')) if exercise_obj else (None, False)
        if not exercise:
            logger.warning("exercise not resolved from submission_url '%s'", self.submission_url)
            return HttpResponseBadRequest("exercise not found from provided submission_url")
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
        kwargs['all_tags'] = tags
        return super().get(request, *args, **kwargs)


def get_tag_list(tags, feedback, get_tag_url=None):
    active = feedback.tags.all()
    return (
        obj_with_attrs(tag,
                       is_active=(tag in active),
                       data_attrs=({'url': get_tag_url(feedback, tag)} if get_tag_url else None))
        for tag in tags
    )


def get_feedback_dict(feedback, get_form, response_form_class,
                      get_post_url=None, get_status_url=None,
                      tags=None, get_tag_url=None):
    form = get_form(feedback)
    data = {
        'form': response_form_class(instance=feedback),
        'feedback': feedback,
         # TODO: keep tags in some consistent order
        'feedback_tags': set(feedback.tags.all()),
        'feedback_form': form,
        'feedback_form_grading': feedback.max_grade > 1 and (form.is_dummy_form or form.is_graded)
    }
    if get_post_url:
        data['post_url'] = get_post_url(feedback)
    if get_status_url:
        data['status_url'] = get_status_url(feedback)
    if tags:
        data['tags'] = get_tag_list(tags, feedback, get_tag_url)
    return data


def update_context_for_feedbacks(request, context, course=None, feedbacks=None, get_form=None, post_url=True):
    # defaults for parameters
    if not course:
        course = context['course']
    if not feedbacks:
        feedbacks = context['object_list']
    if not get_form:
        get_form = lambda o: o.get_form_obj(dummy=True)
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
        query_func=lambda f: {'student': f.student.id, 'exercise': f.exercise.id},
    )

    # all_feedbacks_url
    get_all_feedbacks_url = get_url_reverse_resolver(
        'feedback:list',
        ('course_id',),
        lambda o: (course_id,),
        query_func=lambda f: {'student': f.student.id, 'flags': 'n'},
    )

    # all_feedbacks_for_exercise_url
    get_all_feedbacks_for_exercise_url = get_url_reverse_resolver(
        'feedback:list',
        ('course_id',),
        lambda o: (course_id,),
        query_func=lambda f: {'exercise': f.exercise.id, 'flags': 'n'},
    )

    # get_tag_url
    tags = CachedTags.get(course)
    get_tag_url = get_url_reverse_resolver('feedback:tag',
                                           ('feedback_id', 'tag_id'),
                                           lambda f, t: (f.id, t.id))


    context['feedbacks'] = NestedDictIterator.from_iterable(
        feedbacks,
        (
            ('student', lambda feedback, iterable: {
                'feedback': feedback,
                'student': feedback.student,
                'all_feedbacks_url': get_all_feedbacks_url(feedback),
                'feedbacks_per_student': iterable,
            }),
            ('exercise', lambda feedback, iterable: {
                'feedback': feedback,
                'exercise': feedback.exercise,
                'num_submissions': Feedback.objects.filter(exercise=feedback.exercise, student=feedback.student).count(),
                'all_feedbacks_for_exercise_url' : get_all_feedbacks_for_exercise_url(feedback),
                'all_student_feedbacks_for_exercise_url': get_all_student_feedbacks_for_exercise_url(feedback),
                'feedbacks_per_exercise': iterable,
            }),
        ),
        partial(
            get_feedback_dict,
            get_form=get_form,
            response_form_class=ResponseForm,
            get_post_url=get_post_url,
            get_status_url=get_status_url,
            tags=tags,
            get_tag_url=get_tag_url,
        )
    )


class ManageNotRespondedListView(ManageCourseMixin, ListView):
    model = Feedback
    template_name = "manage/feedback_unread.html"
    paginate_by = 10

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


class ManageFeedbacksListView(ManageCourseMixin, ListView):
    model = Feedback
    template_name = "manage/feedback_list.html"
    paginate_by = 10

    def get_queryset(self):
        course = self.course
        queryset = Feedback.objects.filter(exercise__course=course)
        self.feedback_filter = filter = FeedbackFilter(self.request.GET, queryset, course=course)
        return filter.qs

    def get_context_data(self, **kwargs):
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
        def get_feedback(f):
            f['exercise'] = exercise = exercises[f['exercise_id']]
            f['exercise_path'] = Feedback.get_exercise_path(exercise, f['path_key'])
            return f
        context['feedbacks'] = (get_feedback(feedback) for feedback in feedbacks)
        context['student'] = self.student
        return context


class UserFeedbackView(ManageCourseMixin, TemplateView):
    model = Feedback
    template_name = "manage/user_feedback.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        student_id = self.kwargs['user_id']
        exercise_id = self.kwargs['exercise_id']
        student = get_object_or_404(Student, pk=student_id)
        exercise = get_object_or_404(Exercise.objects.with_course(), pk=exercise_id, course=self.course)
        feedbacks = (
            obj_with_attrs(obj, student=student, exercise=exercise)
            for obj in self.model.objects.all()
                .filter(student=student, exercise=exercise)
                .order_by('-timestamp')
        )
        form_cache = FormCache()
        update_context_for_feedbacks(self.request, context,
            feedbacks=feedbacks, get_form=form_cache.get)
        context['student'] = student
        context['exercise'] = exercise
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
        context['feedbacks'] = feedbacks = context['feedbacks'].get_list(flatten_last=True)
        context.update(feedbacks[-1])
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
        if isinstance(result, HttpResponseRedirect) and self.request.is_ajax():
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
        view = ajax_view if request.is_ajax() else normal_view
        return view(request, *args, **kwargs)
    return dispatch


class FeedbackTagMixin(ManageCourseMixin):
    model = FeedbackTag
    form_class = FeedbackTagForm
    pk_url_kwarg = 'tag_id'
    context_object_name = "tag"

    def get_success_url(self):
        return reverse('feedback:tags', kwargs={'course_id': self.course.id})


class FeedbackTagEditView(FeedbackTagMixin, UpdateView):
    template_name = "feedback_tags/tag_edit.html"


class FeedbackTagDeleteView(FeedbackTagMixin, DeleteView):
    template_name = "feedback_tags/tag_confirm_delete.html"


class FeedbackTagListView(FeedbackTagMixin, ListCreateView):
    template_name = "feedback_tags/tag_list.html"
    context_object_name = "tags"

    def get_queryset(self):
        return self.model.objects.filter(course=self.course)

    def get_form_kwargs(self):
        self.object = self.model(course=self.course)
        return super().get_form_kwargs()


class FeedbackTagView(CheckManagementPermissionsMixin, View):
    permission_classes = [AdminOrTagStaffPermission]

    @cached_property
    def tag_objects(self):
        kwargs = self.kwargs
        feedback_id = kwargs['feedback_id']
        tag_id = kwargs.get('tag_id')
        feedback = get_object_or_404(Feedback, id=feedback_id)
        tag = get_object_or_404(FeedbackTag, id=tag_id) if tag_id is not None else None
        return (feedback, tag)

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        feedback, tag = self.tag_objects
        context['feedback'] = feedback
        return context

    def put(self, *args, **kwargs):
        feedback, tag = self.tag_objects
        if feedback.exercise.course != tag.course:
            return HttpResponseBadRequest("Tag and feedback are not part of same course")
        feedback.tags.add(tag)
        return HttpResponse("ok")

    def delete(self, *args, **kwargs):
        feedback, tag = self.tag_objects
        feedback.tags.remove(tag)
        return HttpResponse("ok")
