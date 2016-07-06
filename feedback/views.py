from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import FormView, ListView

from aplus_client.views import AplusGraderMixin
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


def model_as_string(model):
    from django.forms.models import model_to_dict
    import json
    class SimpleEncoder(json.JSONEncoder):
        def default(self, o):
            return str(o)
    dict_ = model_to_dict(model)
    str_ = json.dumps(dict_, sort_keys=True, indent=4, cls=SimpleEncoder)
    return str_


class FeedbackList(ListView):
    model = Feedback

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


class FeedbackSubmission(AplusGraderMixin, FormView):
    template_name = 'feedback/feedback_form.html'
    success_url = '/feedback/'

    def get_form_class(self):
        data = self.grading_data.exercise._get_item('form_spec') if self.grading_data else None
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
        return context

    def form_valid(self, form):
        students = self.grading_data.students
        if len(students) != 1:
            return HttpResponseBadRequest('this grading service supports only single user submissions')

        # will create and save new feedback
        # will also take care of marking old feedbacks
        new = Feedback.create_new_version(
            course_id = self.kwargs['course_id'],
            group_path = self.kwargs['group_path'],
            user_id = students[0].user_id,
            form_data = form.cleaned_data,
        )

        #s = model_as_string(new)
        #print(" -- NEW FEEDBACK: ", s)
        #return HttpResponse('<pre>%s</pre>' % (s,))
        return super().form_valid(form)

    def form_invalid(self, form):
        # update cached form definition and reparse input
        return super().form_invalid(form)
