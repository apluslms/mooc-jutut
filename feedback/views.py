from urllib.parse import urljoin, urlencode
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.generic import FormView, UpdateView, ListView, TemplateView
from django.core.urlresolvers import reverse

from aplus_client.views import AplusGraderMixin
from lib.postgres import PgAvg
from lib.mixins import CSRFExemptMixin

from .models import Feedback, Student
from .forms import (
    DummyForm,
    DynamicForm,
    ResponseForm,
)



# Feedback a-plus interface
# -------------------------


TEST_FORM = [
    dict(type='textarea', key='message', title='Feedback message', placeholder='Write your feedback here'),
    dict(type='help', value='You should think your answer a bit'),
    dict(disabled=True, title="Not everything is editable"),
    dict(type='number', key='timespent', title='Time Spent', description='Time spent writing this feedback', value=10),
    dict(key='select1', type='string', value='foo', title="Dropdown",
         enum=['bar', 'fooba', 'foo', 'baz'],
         titleMap={'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ', 'fooba': 3}),
    dict(key='select2', type='radios', value='foo', title="Radioselect",
         enum=['bar', 'fooba', 'foo', 'baz'],
         titleMap={'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ', 'fooba': 3}),
    dict(key='select3', type='integer', value='2', title="Few numbers",
         enum=range(4)),
    dict(key='select4', type='integer', value='2', title="Nany numbers",
         enum=range(20)),
]


class FeedbackAverageView(ListView):
    """Example of postgresql json aggregation. Remove when used in analysis"""
    model = Feedback
    template_name = 'feedback_avglist.html'

    def get_queryset(self):
        return Feedback.objects.all(
        ).values(
            'course_id',
            'group_path',
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
    template_name = 'feedback/feedback_form.html'
    success_url = '/feedback/'

    def get_form_class(self):
        data = self.grading_data.exercise.exercise_info._get_item('form_spec') if self.grading_data else None
        if not data and settings.DEBUG:
            data = TEST_FORM

        if data:
            return DynamicForm.get_form_class_by(data)
        elif not self.request.method.lower() in ("get", "head"):
            return DymmyForm
        else:
            raise Http404

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['course'] = self.kwargs.get('course_id', '-')
        context['key'] = self.kwargs.get('group_path', '-')
        context['post_url'] = self.post_url or ''
        return context

    def form_valid(self, form):
        students = self.grading_data.students
        if len(students) != 1:
            return HttpResponseBadRequest('this grading service supports only single user submissions')

        # will create and save new feedback
        # will also take care of marking old feedbacks
        student = Student.create_or_update(students[0])
        new = Feedback.create_new_version(
            course_id = self.kwargs['course_id'],
            group_path = self.kwargs['group_path'],
            student = student,
            form_data = form.cleaned_data,
            submission_url = self.submission_url,
        )

        return self.render_to_response(self.get_context_data(status='accepted'))

    def form_invalid(self, form):
        # update cached form definition and reparse input
        return super().form_invalid(form)



# Feedback management (admin)
# ---------------------------

class UnRespondedFeedbackListView(ListView):
    model = Feedback
    form_class = ResponseForm

    def get_queryset(self):
        course_id = self.kwargs.get('course_id')
        group_filter = self.kwargs.get('group_filter', '').rstrip('/')
        qs = Feedback.objects.all().filter(
            course_id=course_id,
            superseded_by=None,
            response='',
        ).exclude(
            submission_url='',
        )
        if group_filter:
            qs = qs.filter(group_path__startswith=group_filter)
        return qs.order_by('timestamp')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = '?' + urlencode({"success_url": self.request.path})
        context['feedbacks'] = (
            {
                'form': self.form_class(instance=obj),
                'feedback': obj,
                'post_url': urljoin(
                    reverse('feedback:respond', kwargs={'feedback_id': obj.id}),
                    params),
                'older_url': reverse('feedback:byuser', kwargs={
                    'user_id': obj.student.user_id,
                    'course_id': obj.course_id,
                    'group_path': obj.group_path,
                })
            } for obj in context['object_list']
        )
        return context


class UserListView(ListView):
    model = Student
    queryset = model.objects.all()
    template_name = "feedback/user_list.html"
    context_object_name = "students"


class UserFeedbackListView(ListView):
    model = Feedback
    template_name = "feedback/user_feedback_list.html"
    context_object_name = "feedbacks"

    def get_queryset(self):
        self.student = get_object_or_404(Student, user_id=self.kwargs['user_id'])
        return self.model.objects.feedback_groups_for(self.student)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['student'] = self.student
        return context


class UserFeedbackView(TemplateView):
    model = Feedback
    form_class = ResponseForm
    template_name = "feedback/user_feedback.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        feedbacks = self.model.objects.all().filter(
            course_id = self.kwargs['course_id'],
            student_id = self.kwargs['user_id'],
            group_path = self.kwargs['group_path'],
        ).order_by('timestamp')
        params = '?' + urlencode({"success_url": self.request.path})
        context['feedbacks'] = (
            {
                'form': self.form_class(instance=obj),
                'feedback': obj,
                'post_url': urljoin(
                    reverse('feedback:respond', kwargs={'feedback_id': obj.id}),
                    params),
            } for obj in feedbacks
        )
        return context


class RespondFeedbackView(UpdateView):
    model = Feedback
    form_class = ResponseForm
    template_name = "feedback/response_form.html"
    context_object_name = 'feedback'
    pk_url_kwarg = 'feedback_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        success_url = self.request.GET.get('success_url')
        if success_url:
            me = self.request.path
            params = '?' + urlencode({"success_url": success_url})
            context['post_url'] = urljoin(me, params)
        return context

    def get_success_url(self):
        url = self.request.GET.get('success_url')
        if not url:
            url = reverse('feedback:notresponded', kwargs={
                'course_id': self.object.course_id,
                'group_filter': self.object.group_path,
            })
        return url
