from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import FormView, ListView

from lib.postgres import PgAvg

from .models import Feedback
from .forms import DummyForm, DynamicForm


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


class FeedbackList(ListView):
    model = Feedback

    def get_queryset(self):
        return Feedback.objects.all(
        ).values(
            'course_id',
            'group_path',
        ).filter(
            form_data__has_key='timespent'
        ).annotate(
            avg=PgAvg('form_data', 'timespent')
        )


class FeedbackSubmission(FormView):
    template_name = 'feedback/feedback_form.html'
    success_url = '/feedback/'

    def get_form_class(self):
        data = self.request.GET.get('form', None)
        if not data and settings.DEBUG:
            data = TEST_FORM
        if data:
            return DynamicForm.get_form_class_by(data)

        if not self.request.method.lower() in ("get", "head"):
            return DymmyForm
        raise Http404

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['course'] = self.kwargs.get('course_id', '-')
        context['key'] = self.kwargs.get('exercise_path', '-')
        return context

    def form_valid(self, form):
        feedback = form.cleaned_data

        print(feedback)
        return HttpResponse('<pre>%s</pre>' % (feedback,))

    def form_invalid(self, form):
        # update cached form definition and reparse input
        return super().form_invalid(form)

    def post(self, request, *args, **kwargs):
        user_id = self.request.GET.get('uid', None)
        if not user_id:
            return HttpResponseBadRequest('this grading service requires uid parameter')
        if '-' in user_id:
            return HttpResponseBadRequest('this grading service supports only single user submissions')
        try:
            user_id = int(user_id)
        except ValueError:
            return HttpResponseBadRequest('this grading service requires int type uid parameter')

        return super().post(request, *args, **kwargs)
