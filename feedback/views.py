from urllib.parse import urljoin, urlencode
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.generic import FormView, UpdateView, ListView, TemplateView
from django.core.urlresolvers import reverse
from django.core.exceptions import SuspiciousOperation

from aplus_client.django.views import AplusGraderMixin
from dynamic_forms.forms import DummyForm, DynamicForm
from lib.postgres import PgAvg
from lib.mixins import CSRFExemptMixin

from .models import Feedback, Student, Form
from .forms import ResponseForm



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


class SuspiciousStudent(SuspiciousOperation):
    pass


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

    def load_form_spec_from_grading_data(self):
        if self.grading_data:
            return self.grading_data.form_spec

    def get_form_class(self):
        self.course_id = course_id = self.kwargs['course_id']
        self.group_path = group_path = self.kwargs['group_path']

        # load form_spec from database
        form_obj = Form.objects.latest_for(course_id=course_id, group_path=group_path)
        form_spec = form_obj.form_spec if form_obj else None

        # if there is nm form_spec in db load from exercise_info
        if not form_spec:
            form_spec = self.load_form_spec_from_grading_data()
            if form_spec:
                form_obj = Form.objects.create(course_id=course_id,
                                               group_path=group_path,
                                               form_spec=form_spec)

        # if there still is no form_spec and we are in DEBUG use TEST_FORM
        if not form_spec and settings.DEBUG:
            form_spec = TEST_FORM

        self.form_spec = form_spec
        self.form_obj = form_obj

        if form_spec:
            return DynamicForm.get_form_class_by(form_spec)
        elif not self.request.method.lower() in ("get", "head"):
            return DymmyForm
        else:
            raise Http404

    def get_student(self):
        student = None

        # Try to resolve student using uid from query parameters
        uids = self.request.GET.get('uid', '').split('-')
        if len(uids) > 1:
            raise SuspiciousStudent("Multiple uids in query uid field")
        if len(uids) == 1:
            try:
                student = Student.objects.get(user_id=uids[0])
            except (Student.DoesNotExist, ValueError):
                pass

        # Fallback to resolve student from grading_data
        if not student:
            students = self.grading_data.submitters
            if len(students) != 1:
                raise SuspiciousStudent("Multiple students in grading_data")
            student = Student.create_or_update(students[0])

        return student

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['post_url'] = self.post_url or ''
        return context

    def form_valid(self, form):
        student = self.get_student()

        # will create and save new feedback
        # will also take care of marking old feedbacks
        new = Feedback.create_new_version(
            course_id = self.course_id,
            group_path = self.group_path,
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
        # update cached form definition and reparse input
        if self.form_obj.could_be_updated:
            form_spec = self.load_form_spec_from_grading_data()
            form_obj = self.form_obj.get_updated(form_spec)
            if form_obj == self.form_obj:
                # FIXME: trigger validate again
                pass

        return super().form_invalid(form)



# Feedback management (admin)
# ---------------------------

class UnRespondedFeedbackListView(ListView):
    model = Feedback
    form_class = ResponseForm

    def get_queryset(self):
        course_id = self.kwargs.get('course_id')
        group_filter = self.kwargs.get('group_filter', '').rstrip('/')
        return Feedback.objects.get_unresponded(course_id, group_filter)

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
