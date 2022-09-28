from django.db import transaction
from django.core.management.base import BaseCommand

from ..command_utils import get_feedback_queryset
from ...models import Feedback

class Command(BaseCommand):
    help = 'Rebuild superseded references based on submission time'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--feedback',
                            type=int, default=None,
                            help="Reload single feedback (use id)")
        parser.add_argument('-s', '--site',
                            help="Domain of aplus site or 'all'")
        parser.add_argument('-c', '--course',
                            help="If there is more than one course, "
                            "give code of the course you are reloading or 'all'")

    def handle(self, *args, **options):
        feedbacks, feedbacks_count = get_feedback_queryset(
            self,
            options['feedback'],
            options['site'],
            options['course'],
        )

        if feedbacks_count == 1:
            fb = feedbacks[0]
            feedbacks = Feedback.objects.all().filter(
                student=fb.student, exercise=fb.exercise)
            feedbacks_count = feedbacks.count()

        feedbacks = ( feedbacks
            .order_by('timestamp', 'id')
            .select_related(None)
            .only('exercise', 'student', 'timestamp')
        )

        with transaction.atomic():
            feedbacks.update(superseded_by=None)
            for feedback in feedbacks:
                self.stdout.write(self.style.NOTICE("Working on {} from {}".format(feedback.id, feedback.timestamp)))
                feedback.supersede_older()
