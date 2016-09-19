import time
from django.core.management.base import BaseCommand, CommandError

from aplus_client.client import AplusGraderClient

from ..command_utils import get_feedback_queryset
from ...models import Student, Feedback


class Command(BaseCommand):
    help = 'Reload submission data from aplus'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--feedback',
                            type=int, default=None,
                            help="Reload single feedback (use id)")
        parser.add_argument('-s', '--site',
                            help="Domain of aplus site or 'all'")
        parser.add_argument('-c', '--course',
                            help="If there is more than one course, give code of the course you are reloading or 'all'")
        parser.add_argument('--meta',
                            action='store_true',
                            help="Reload submission metadata")
        parser.add_argument('--content',
                            action='store_true',
                            help="Reload submission form content")
        parser.add_argument('--wait',
                            type=int, default=200,
                            help="How long to wait between updating two feedbacks in milliseconds")

    def handle(self, *args, **options):
        wait = options['wait']/1000
        update_meta = options['meta']
        update_content = options['content']

        feedbacks, feedbacks_count = get_feedback_queryset(
            self,
            options['feedback'],
            options['site'],
            options['course'],
        )

        if not any((update_meta, update_content)):
            raise CommandError("No update action given")

        if update_content:
            raise NotImplementedError("udpating content is not yet supported")

        feedbacks = feedbacks.order_by('-timestamp', '-id')

        def load_grading_data(client):
            gd = client.grading_data
            # make sure all required resources are loaded
            try:
                eid = gd.data.submission.exercise.id if update_meta else -1
            except AttributeError:
                eid = None
            ok = eid is not None
            return gd, ok

        for feedback in feedbacks:
            submission_url = feedback.submission_url
            self.stdout.write(self.style.NOTICE("Working on {}, {}".format(feedback.id, submission_url)))
            client = AplusGraderClient(submission_url, debug_enabled=True)
            fields = []

            # get grading data
            for i in range(100):
                gd, gd_ok = load_grading_data(client)
                if gd_ok:
                    break
                sleep_for = wait + (i*wait/10)
                self.stdout.write(self.style.NOTICE("ERROR: failed to get grading data.. sleeping for {}s".format(sleep_for)))
                time.sleep(sleep_for)
            if not gd_ok:
                self.stdout.write(self.style.NOTICE("ERROR: failed to get grading data.. giving up"))
                break

            if update_meta:
                # submitter / student
                students = gd.submitters
                if not students:
                    self.stdout.write(self.style.ERROR("  No students found from api. Not updating submitters."))
                elif len(students) != 1:
                    self.stdout.write(self.style.ERROR("  Multiple students in submission. Feedback expects only one. Not updating submitters."))
                else:
                    student = Student.objects.get_new_or_updated(students[0], namespace=feedback.exercise.namespace)
                    if feedback.student != student:
                        self.stdout.write(self.style.SUCCESS("  Updating student from '{}' to '{}'".format(feedback.student, student)))
                        feedback.student = student
                        fields.append('student')

                # submission id
                submission_id = gd.submission_id
                if not Feedback.objects.filter(exercise=feedback.exercise, submission_id=submission_id).exists():
                    feedback.submission_id = submission_id
                    fields.append('submission_id')

                # simple meta fields
                metamap = {
                    'timestamp': 'submission_time',
                    'submission_html_url': 'html_url',
                }
                for field, src in metamap.items():
                    val = getattr(gd, src, None)
                    cur = getattr(feedback, field, None)
                    if val and val != cur:
                        self.stdout.write(self.style.SUCCESS("  Updating {} from '{}' to '{}'".format(field, cur, val)))
                        setattr(feedback, field, val)
                        fields.append(field)


            # safe changed data
            feedback.save(fields)

            # sleep for some time, so we don't flood api service
            time.sleep(wait)
