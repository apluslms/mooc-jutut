from django.views.generic import ListView
from feedback.views import ManageCourseMixin, update_context_for_feedbacks
from feedback.models import Feedback
from feedback.filters import FeedbackFilter

from plotly.offline import plot
from plotly.graph_objs import Bar, Figure, Layout

class TimeUsageView(ManageCourseMixin, ListView):

    model = Feedback
    template_name = "time_usage.html"
    def plot_times(self):
        feedbacks = self.get_queryset()
        feedbacks_by_exercise = {}

        for f in feedbacks:
            feedbacks_by_exercise.setdefault(f.exercise, []).append(f)

        x_data = []
        md_data = [] # medians
        perc75_data = [] # 75th percentiles
        md_by_round = {}
        p75_by_round = {}
        for e, flist in feedbacks_by_exercise.items():
            times = [f.form_data.get('timespent') for f in flist]
            times = [time for time in times if time is not None]
            if times:
                times = sorted(times)
                len_times = len(times)
                mid_idx = (len_times - 1) // 2
                md = times[mid_idx] if len_times % 2 else (times[mid_idx] + times[mid_idx+1]) / 2.0
                perc75 = times[int(round(0.75 * len_times + 0.5)) - 1]
                xname = '.'.join(e.display_name.split('.')[:2])
                #count sums by round
                rd = xname.split('.')[0]
                md_by_round[rd] = md if rd not in md_by_round else md_by_round[rd] + md
                p75_by_round[rd] = perc75 if rd not in p75_by_round else p75_by_round[rd] + perc75

                x_data.append(xname)
                md_data.append(md)
                perc75_data.append(perc75)

        chapter_times = plot(
            Figure(
                [
                    Bar(name = '75th%', x = x_data, y = perc75_data, marker_color = '#00adf0'),
                    Bar(name = 'median', x = x_data, y = md_data, marker_color = '#0077b4')
                ],
                layout = Layout(xaxis_title='chapter', yaxis_title='minutes', barmode='overlay')
            ),
            output_type='div'
        )

        rounds_p75, p75 = zip(*p75_by_round.items())
        rounds_md, md = zip(*md_by_round.items())
        round_times = plot(
            Figure(
                [Bar(name = '75th% weekly sum', x = rounds_p75, y = p75, marker_color = '#00adf0'),
                Bar(name = 'median weekly sum', x = rounds_md, y = md, marker_color = '#0077b4')],
                layout = Layout(xaxis={'tickformat': ',d', 'title': 'round'}, yaxis_title='minutes', barmode='overlay')
            ),
            output_type='div'
        )

        return chapter_times, round_times



    def get_queryset(self):
        course = self.course
        queryset = Feedback.objects.filter(exercise__course=course, superseded_by=None)
        self.feedback_filter = filter = FeedbackFilter(self.request.GET, queryset, course=course)
        return filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(course=self.course, **kwargs)
        context['feedback_filter'] = self.feedback_filter
        context['c_plot'], context['r_plot'] = self.plot_times()
        update_context_for_feedbacks(self.request, context)
        return context
