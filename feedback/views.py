import logging
from datetime import timedelta
from functools import partial
from urllib.parse import urljoin, urlencode
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, Http404
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
    CachedSites,
    CachedCourses,
    CachedNotrespondedCount,
)
from .forms import ResponseForm


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

    def get_form_class(self):
        self.path_key = path_key = self.kwargs.get('path_key', '').strip('/')
        gd = self.grading_data
        exercise = gd.exercise

        if not exercise:
            logger.critical("exercise not resolved from submission_url '%s'", self.submission_url)
            raise Http404("exercise not found from provided submission_url")

        # get or create exercise for this request that has correct namespace
        # (gotten from exercise api_obj url field)
        exercise, created = Exercise.objects.get_or_create(exercise)
        self.exercise = exercise


        # get latest form object or create new
        form_obj = exercise.get_latest_form(path_key, max_age=timedelta(minutes=5))
        if form_obj is None:
            form_spec = gd.form_spec
            if form_spec:
                form_obj = Form.objects.get_or_create(form_spec=form_spec)

        if form_obj:
            self.form_obj = form_obj
            auto_id = "jutut_ex{}_%s".format(exercise.api_id)
            return partial(form_obj.form_class, auto_id=auto_id)
        else:
            logger.critical("form_spec not resolved from submission_url '%s'", self.submission_url)
            raise Http404("form_spec not found from provided submission_url")

    def get_student(self):
        student = None

        # Try to resolve student using uid from query parameters
        uids = self.request.GET.get('uid', '').split('-')
        if len(uids) > 1:
            raise SuspiciousStudent("Multiple uids in query uid field")
        if len(uids) == 1:
            try:
                student = Student.objects.get(id=uids[0])
            except (Student.DoesNotExist, ValueError):
                pass

        # Fallback to resolve student from grading_data
        if not student:
            students = self.grading_data.submitters
            if len(students) != 1:
                raise SuspiciousStudent("Multiple students in submission. Feedback expects only one")
            student = Student.objects.get_new_or_updated(students[0])

        return student

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['exercise'] = self.exercise
        context['post_url'] = self.post_url or ''
        return context

    def form_valid(self, form):
        student = self.get_student()
        path_key = self.path_key

        # will create and save new feedback
        # will also take care of marking old feedbacks
        new = Feedback.create_new_version(
            exercise = self.exercise,
            path_key = path_key,
            student = student,
            form = self.form_obj,
            form_data = form.cleaned_data,
            post_url = self.post_url or '',
            submission_url = self.submission_url or '',
        )

        return self.render_to_response(self.get_context_data(
            status='accepted',
            feedback=new,
        ))

    def form_invalid(self, form):
        # FIXME: trigger validate again
        # update cached form definition and reparse input
        #if self.form_obj.could_be_updated:
        #    form_spec = self.grading_data.form_spec
        #    form_obj = self.form_obj.get_updated(form_spec)
        #    if form_obj == self.form_obj:
        #        pass

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


class ManageNotRespondedListView(LoginRequiredMixin,
                                 ManageCourseMixin,
                                 ListView):
    model = Feedback
    template_name = "manage/feedback_list.html"
    form_class = ResponseForm

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
        course=self._course
        context = super().get_context_data(course=course, **kwargs)
        params = '?' + urlencode({"success_url": self.request.path})
        context['exercise'] = self._exercise
        context['path_filter'] = self._path_filter
        context['feedbacks'] = (
            {
                'form': self.form_class(instance=obj),
                'feedback': obj,
                'post_url': urljoin(
                    reverse('feedback:respond', kwargs={'feedback_id': obj.id}),
                    params),
                'older_url': reverse('feedback:byuser', kwargs={
                    'course_id': course.id,
                    'user_id': obj.student.id,
                    'exercise_id': obj.exercise.id,
                }),
            } for obj in context['object_list']
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
        params = '?' + urlencode({"success_url": self.request.path})
        def _w(obj, **kwargs):
            for k, v in kwargs.items():
                setattr(obj, k, v)
            return obj
        context['feedbacks'] = (
            {
                'form': self.form_class(instance=obj),
                'feedback': obj,# exercise=exercise),
                'post_url': urljoin(
                    reverse('feedback:respond', kwargs={'feedback_id': obj.id}),
                    params),
            } for obj in feedbacks
        )
        context['student'] = student
        context['exercise'] = exercise
        return context


class RespondFeedbackView(LoginRequiredMixin,
                          ManageCourseMixin,
                          UpdateView):
    model = Feedback
    form_class = ResponseForm
    template_name = "manage/response_form.html"
    context_object_name = 'feedback'
    pk_url_kwarg = 'feedback_id'
    success_url_param = 'success_url'

    def get_context_data(self, **kwargs):
        feedback = self.object
        context = super().get_context_data(course=feedback.exercise.course, **kwargs)
        success_url = self.request.GET.get(self.success_url_param)
        if success_url:
            me = self.request.path
            params = '?' + urlencode({self.success_url_param: success_url})
            context['post_url'] = urljoin(me, params)
        return context

    def get_success_url(self):
        if self.request.is_ajax():
            # skip redirect url resolving for ajax request, as it will be replaced
            return "ajax"
        url = self.request.GET.get(self.success_url_param)
        if not url:
            url = reverse('feedback:notresponded-exercise', kwargs={
                'exercise_id': self.object.form.exercise.id,
            })
        return url

    def form_valid(self, form):
        result = super().form_valid(form)
        if isinstance(result, HttpResponseRedirect) and self.request.is_ajax():
            # return form as we would have done with invalid case, but signal client with 201 code that it was created
            logger.debug("Ajax POST ok, returning original form with status 201")
            return self.render_to_response(self.get_context_data(form=form), status=201)
        return result


class RespondFeedbackViewAjax(LoginRequiredMixin,
                              UpdateView):
    model = Feedback
    form_class = ResponseForm
    template_name = "manage/response_form_ajax.html"
    context_object_name = 'feedback'
    pk_url_kwarg = 'feedback_id'
    success_url_param = RespondFeedbackView.success_url_param

    def get_context_data(self, **kwargs):
        feedback = self.object
        context = super().get_context_data(course=feedback.exercise.course, **kwargs)
        success_url = self.request.GET.get(self.success_url_param)
        if success_url:
            me = self.request.path
            params = '?' + urlencode({self.success_url_param: success_url})
            context['post_url'] = urljoin(me, params)
        return context

    def get_success_url(self):
        # skip redirect url resolving for ajax request, as it will be replaced
        return None

    def form_valid(self, form):
        result = super().form_valid(form)
        if isinstance(result, HttpResponseRedirect):
            # return form as we would have done with invalid case, but signal client with 201 code that it was created
            logger.debug("Ajax POST ok, returning original form with status 201")
            return self.render_to_response(self.get_context_data(form=form), status=201)
        return result


def respond_feedback_view_select(normal_view, ajax_view):
    def dispatch(request, *args, **kwargs):
        view = ajax_view if request.is_ajax() else normal_view
        print(" ----- suing view: ", view)
        return view(request, *args, **kwargs)
    return dispatch
