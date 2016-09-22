import logging
from datetime import timedelta
from functools import partial
from urllib.parse import urlsplit, urljoin, urlencode
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.utils.text import slugify
from django.utils.timezone import now as timezone_now
from django.shortcuts import get_object_or_404
from django.views.generic import FormView, UpdateView, ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.urlresolvers import reverse
from django.core.exceptions import SuspiciousOperation

from lib.postgres import PgAvg
from lib.mixins import CSRFExemptMixin
from aplus_client.django.views import AplusGraderMixin
from dynamic_forms.models import Form

from .models import (
    Site,
    Course,
    Exercise,
    Student,
    Form,
    Feedback,
)
from .cached import (
    FormCache,
    CachedForm,
    CachedSites,
    CachedCourses,
    CachedNotrespondedCount,
    clear_cache,
)
from .forms import ResponseForm
from .filters import FeedbackFilter
from .utils import (
    get_url_reverse_resolver,
    obj_with_attrs,
    augment_form_with_optional_field_info,
    augment_form_with_optional_answers_info,
    form_can_be_autoaccepted,
    is_grade_restricted_to_good,
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
                form_obj = CachedForm.get(cache_key, lambda: self.grading_data.form_spec)
            except ValueError:
                pass

        # if we can't use cache, use the "old way"
        else:
            form_spec = self.grading_data.form_spec
            if form_spec:
                form_obj = Form.objects.get_or_create(form_spec=form_spec)

        if form_obj:
            self.form_obj = form_obj
            auto_id = "jutut_{}_%s".format(slugify(post_url.path or path_key))
            self.form_class = form_class = partial(form_obj.form_class, auto_id=auto_id)
            return form_class
        else:
            logger.critical("form_spec not resolved from submission_url '%s'", self.submission_url)
            raise Http404("form_spec not found from provided submission_url")

    def reload_form_class(self):
        cache_key = self.form_cache_key
        if cache_key:
            form_obj_id = getattr(self.form_obj, 'id', None)
            CachedForm.clear(cache_key, lambda: None)
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
        context['post_url'] = self.post_url or ''
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

        # Common data for feedback
        data = {
            'student': student,
            'form': self.form_obj,
            'form_data': form.cleaned_data,
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
            # will create and save new feedback
            # will also take care of marking old feedbacks
            feedback = Feedback.create_new_version(
                exercise = exercise,
                submission_id = gd.submission_id,
                path_key = path_key,
                **data,
            )

        # test if feedback can be automatically accepted
        if settings.JUTUT_AUTOACCEPT_ON:
            augment_form_with_optional_field_info(form)
            augment_form_with_optional_answers_info(form)
            can_be_autoaccepted = form_can_be_autoaccepted(form)
        else:
            can_be_autoaccepted = False

        if can_be_autoaccepted:
            logger.warning("Feedback %d could have been automatically accepted.", feedback.id)

        status = 'graded' if feedback.responded else 'accepted'
        return self.render_to_response(self.get_context_data(status=status, feedback=feedback))

    def form_invalid(self, form):
        if self.reload_form_class():
            form = self.get_form()
            if form.is_valid():
                return self.form_valid(form)
        return super().form_invalid(form)



# Feedback management (admin)
# ---------------------------

class ManageSiteMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sitelist'] = CachedSites.get
        site = context.get('site', None)
        if site:
            context['sitename'] = '.'.join(site.domain.split('.', 2)[:2])
            context['courselist'] = CachedCourses.get(site)
        return context


class ManageCourseMixin(ManageSiteMixin):
    def get_context_data(self, **kwargs):
        course = kwargs['course']
        kwargs.setdefault('site', course.namespace)
        context = super().get_context_data(**kwargs)
        context['course_notresponded'] = CachedNotrespondedCount.get(course)
        return context


class ManageSiteListView(LoginRequiredMixin,
                         ManageSiteMixin,
                         ListView):
    model = Site
    template_name = "manage/site_list.html"
    context_object_name = "sites"


class ManageCourseListView(LoginRequiredMixin,
                           ManageSiteMixin,
                           ListView):
    model = Course
    template_name = "manage/course_list.html"
    context_object_name = "courses"

    def get_queryset(self):
        site_id = self.kwargs.get('site_id', None)
        if site_id is not None:
            self._site = site = get_object_or_404(Site, pk=site_id)
            qs = self.model.objects.using_namespace(site)
        else:
            qs = self.model.objects
        return qs.all().order_by('namespace', 'api_id')

    def get_context_data(self, **kwargs):
        return super().get_context_data(site=self._site, **kwargs)


class ManageClearCacheView(LoginRequiredMixin,
                           ManageCourseMixin,
                           TemplateView):
    template_name = "manage/cache_cleared.html"

    def get_context_data(self, **kwargs):
        course = get_object_or_404(Course, pk=self.kwargs['course_id'])
        return super().get_context_data(course=course)

    def get(self, *args, **kwargs):
        clear_cache()
        return super().get(*args, **kwargs)


def get_feedback_dict(obj, get_form=None, extra=None):
    if get_form:
        form = get_form(obj)
    else:
        form = obj.get_form_obj(dummy=True)
    if settings.JUTUT_OBLY_ACCEPT_ON and not form.is_dummy_form:
        augment_form_with_optional_field_info(form)
        augment_form_with_optional_answers_info(form, use_cleaned_data=False)
        min_grade = obj.MAX_GRADE if is_grade_restricted_to_good(form) else 0
    else:
        min_grade = 0
    data = {
        'feedback': obj,
        'feedback_form': form,
        'min_grade': min_grade,
    }
    if extra:
        data.update(extra)
    return data


class ManageNotRespondedListView(LoginRequiredMixin,
                                 ManageCourseMixin,
                                 ListView):
    model = Feedback
    template_name = "manage/feedback_unread.html"
    form_class = ResponseForm
    paginate_by = 10

    def get_queryset(self):
        kw = self.kwargs

        course_id = kw.get('course_id')
        if course_id is not None:
            self._exercise = None
            self._course = get_object_or_404(Course, pk=course_id)
            self._path_filter = path_filter = self.kwargs.get('path_filter', '').strip('/')
            return Feedback.objects.get_notresponded(course_id=course_id, path_filter=path_filter)

        exercise_id = kw.get('exercise_id')
        if exercise_id is not None:
            self._exercise = get_object_or_404(Exercise.objects.with_course(), pk=exercise_id)
            self._course = self._exercise.course
            self._path_filter = ''
            return Feedback.objects.get_notresponded(exercise_id)

        raise Http404

    def get_context_data(self, **kwargs):
        course = self._course
        context = super().get_context_data(course=course, **kwargs)
        posturl_r = get_url_reverse_resolver('feedback:respond',
            ('feedback_id',),
            urlencode({"success_url": self.request.path}))
        older_r = get_url_reverse_resolver('feedback:byuser',
            ('course_id', 'user_id', 'exercise_id'))
        context['feedbacks'] = (
            get_feedback_dict(obj,
                extra={
                    'form': self.form_class(instance=obj),
                    'older_url': older_r(course_id=course.id,
                                         user_id=obj.student.id,
                                         exercise_id=obj.exercise.id),
                    'post_url': posturl_r(feedback_id=obj.id)
                }
            ) for obj in context['object_list']
        )
        context['exercise'] = self._exercise
        context['path_filter'] = self._path_filter
        return context


class ManageFeedbacksListView(LoginRequiredMixin,
                              ManageCourseMixin,
                              ListView):
    model = Feedback
    template_name = "manage/feedback_list.html"
    form_class = ResponseForm
    paginate_by = 10

    def get_queryset(self):
        self.course = course = get_object_or_404(Course, pk=self.kwargs['course_id'])
        queryset = Feedback.objects.filter(exercise__course=course)
        self.feedback_filter = filter = FeedbackFilter(self.request.GET, queryset, course=course)
        queryset = filter.qs
        if not queryset.ordered:
            queryset.order_by('timestamp')
        return queryset

    def get_context_data(self, **kwargs):
        course = self.course
        context = super().get_context_data(course=course, **kwargs)
        posturl_r = get_url_reverse_resolver('feedback:respond',
            ('feedback_id',),
            urlencode({"success_url": self.request.path}))
        older_r = get_url_reverse_resolver('feedback:byuser',
            ('course_id', 'user_id', 'exercise_id'))
        context['feedback_filter'] = self.feedback_filter
        context['feedbacks'] = (
            get_feedback_dict(obj,
                extra={
                    'form': self.form_class(instance=obj),
                    'older_url': older_r(course_id=course.id,
                                         user_id=obj.student.id,
                                         exercise_id=obj.exercise.id),
                    'post_url': posturl_r(feedback_id=obj.id)
                }
            ) for obj in context['object_list']
        )
        return context


class UserListView(LoginRequiredMixin,
                   ManageCourseMixin,
                   ListView):
    model = Student
    template_name = "manage/user_list.html"
    context_object_name = "students"

    def get_queryset(self):
        course_id = self.kwargs.get('course_id')
        self._course = course = get_object_or_404(Course, pk=course_id)
        return self.model.objects.get_students_on_course(course)

    def get_context_data(self, **kwargs):
        return super().get_context_data(course=self._course, **kwargs)


class UserFeedbackListView(LoginRequiredMixin,
                           ManageCourseMixin,
                           ListView):
    model = Feedback
    template_name = "manage/user_feedback_list.html"
    context_object_name = "feedbacks"

    def get_queryset(self):
        self.course = course = get_object_or_404(Course, pk=self.kwargs['course_id'])
        self.student = student = get_object_or_404(Student, pk=self.kwargs['user_id'])
        return self.model.objects.feedback_exercises_for(course, student)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(course=self.course, **kwargs)
        feedbacks = list(context['feedbacks'])
        exercises = list(set(f['exercise_id'] for f in feedbacks))
        exercises = Exercise.objects.filter(pk__in=exercises)
        exercises = {e.id: e for e in exercises}
        course = self.course
        def get_feedback(f):
            f['exercise'] = exercise = exercises[f['exercise_id']]
            f['exercise_path'] = Feedback.get_exercise_path(exercise, f['path_key'])
            return f
        context['feedbacks'] = (get_feedback(feedback) for feedback in feedbacks)
        context['student'] = self.student
        return context


class UserFeedbackView(LoginRequiredMixin,
                       ManageCourseMixin,
                       TemplateView):
    model = Feedback
    form_class = ResponseForm
    template_name = "manage/user_feedback.html"

    def get_context_data(self, **kwargs):
        course = get_object_or_404(Course, pk=self.kwargs['course_id'])

        context = super().get_context_data(course=course, **kwargs)

        student_id = self.kwargs['user_id']
        exercise_id = self.kwargs['exercise_id']
        student = get_object_or_404(Student, pk=student_id)
        exercise = get_object_or_404(Exercise.objects.with_course(), pk=exercise_id, course=course)
        feedbacks = self.model.objects.all().filter(
            student = student,
            exercise = exercise,
        ).order_by('-timestamp')
        form_cache = FormCache()
        posturl_r = get_url_reverse_resolver('feedback:respond',
            ('feedback_id',),
            urlencode({"success_url": self.request.path}))
        context['feedbacks'] = (
            get_feedback_dict(
                obj_with_attrs(obj, exercise=exercise),
                get_form=form_cache.get,
                extra={
                    'form': self.form_class(instance=obj),
                    'post_url': posturl_r(feedback_id=obj.id)
                }
            ) for obj in feedbacks
        )
        context['student'] = student
        context['exercise'] = exercise
        return context


class RespondFeedbackMixin:
    model = Feedback
    form_class = ResponseForm
    context_object_name = 'feedback'
    pk_url_kwarg = 'feedback_id'
    success_url_param = 'success_url'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        feedback = self.object
        context = super().get_context_data(course=feedback.exercise.course, **kwargs)
        context.update(get_feedback_dict(feedback))
        success_url = self.request.GET.get(self.success_url_param)
        if success_url:
            me = self.request.path
            params = '?' + urlencode({self.success_url_param: success_url})
            context['post_url'] = urljoin(me, params)
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
            url = reverse('feedback:notresponded-exercise', kwargs={
                'exercise_id': self.object.form.exercise.id,
            })
        return url


class RespondFeedbackView(LoginRequiredMixin,
                          RespondFeedbackMixin,
                          ManageCourseMixin,
                          UpdateView):
    template_name = "manage/response_form.html"


class RespondFeedbackViewAjax(LoginRequiredMixin,
                              RespondFeedbackMixin,
                              UpdateView):
    template_name = "manage/response_form_ajax.html"

    def get_success_url(self):
        # skip redirect url resolving for ajax request, as it will be replaced
        return None


def respond_feedback_view_select(normal_view, ajax_view):
    def dispatch(request, *args, **kwargs):
        view = ajax_view if request.is_ajax() else normal_view
        return view(request, *args, **kwargs)
    return dispatch
